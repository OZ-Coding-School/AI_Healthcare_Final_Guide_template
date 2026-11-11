"""
서빙 아티팩트의 저장, 무결성 확인, 로드를 담당합니다.

모델마다 폴더 하나에 학습 산출물을 역할별 파일로 나눠 저장합니다.

    {model_type}_model/
    ├── model.pkl           학습된 분류기
    ├── preprocessor.pkl    Train에만 fit한 전처리기 (결측 대치, 원-핫 등)
    ├── calibrator.pkl      확률 보정기
    ├── thresholds.json     위험 등급 경계와 산출 기준
    └── metadata.json       출처, 입력 스키마, 학습 범위, 버전, 파일 해시

코드값 정제·파생변수 같은 규칙 기반 전처리(KnhanesPreprocessor)는 학습한 상태가 없으므로 파일이 아니라 코드로 적용합니다.
pickle은 로드 시 코드를 실행할 수 있으므로, 매니페스트 → metadata.json → 각 파일 순서로 SHA-256을 확인한 뒤에만 로드합니다.
"""

import hashlib
import json
import logging
import subprocess
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.components.knhanes_inference_errors import ModelArtifactError
from src.components.model_trainer import ModelBundle
from src.enums import ModelType
from src.knhanes_inference_configs import (
    FEATURE_DISPLAY_NAME_MAP,
    SERVING_BUNDLE_SCHEMA_VERSION,
    SERVING_CALIBRATOR_FILE,
    SERVING_HASHED_FILES,
    SERVING_MANIFEST_NAME,
    SERVING_METADATA_FILE,
    SERVING_METADATA_REQUIRED_KEYS,
    SERVING_MODEL_FILE,
    SERVING_PREPROCESSOR_FILE,
    SERVING_THRESHOLDS_FILE,
    SERVING_TRACKED_LIBRARIES,
    serving_model_dirname,
)

logger = logging.getLogger(__name__)

RISK_THRESHOLD_KEYS = {"moderate", "high"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in SERVING_TRACKED_LIBRARIES:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def code_version() -> dict[str, Any]:
    """아티팩트를 만든 코드의 커밋입니다. Git이 없는 환경(컨테이너 등)에서는 None입니다."""
    ai_dir = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ai_dir, capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "src"],
            cwd=ai_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": None, "src_has_uncommitted_changes": None}
    return {"git_commit": commit, "src_has_uncommitted_changes": bool(status.strip())}


def build_input_schema(bundle: ModelBundle, X_train: pd.DataFrame) -> dict[str, Any]:
    """
    전처리기가 학습한 입력 컬럼과 범주형 허용값을 기록합니다.
    OneHotEncoder(handle_unknown="ignore")는 처음 보는 범주를 오류 없이 무시하므로, 추론 전에 이 목록으로 검사합니다.
    """
    columns = [str(column) for column in getattr(bundle.preprocessor, "feature_names_in_", [])]
    if not columns:
        raise ModelArtifactError("Bundle preprocessor has no fitted input columns")
    if X_train.columns.tolist() != columns:
        raise ModelArtifactError("X_train columns differ from the bundle input columns")

    numeric: list[str] = []
    categorical: dict[str, list[str]] = {}
    for name, _, transformer_columns in bundle.preprocessor.transformers_:
        if name == "num":
            numeric.extend(transformer_columns)
        elif name == "cat":
            for column in transformer_columns:
                categorical[column] = sorted(str(value) for value in X_train[column].dropna().unique())
    if set(numeric) | set(categorical) != set(columns):
        raise ModelArtifactError("Bundle transformers do not cover all input columns")
    return {"columns": columns, "numeric": numeric, "categorical": categorical}


def build_numeric_ranges(X_train: pd.DataFrame, numeric_columns: list[str]) -> dict[str, dict[str, float]]:
    """학습 데이터의 수치 범위입니다. 범위를 벗어난 입력은 거부하지 않고 결과에 표시합니다."""
    return {
        column: {"min": float(X_train[column].min()), "max": float(X_train[column].max())} for column in numeric_columns
    }


def build_display_feature_metadata(bundle: ModelBundle) -> list[dict[str, str]]:
    """원-핫 피처까지 원 변수의 표시명을 붙입니다. 표시명이 없는 원 변수가 있으면 거부합니다."""
    if not bundle.feature_metadata:
        raise ModelArtifactError("Bundle has no feature metadata")
    result = []
    missing = set()
    for item in bundle.feature_metadata:
        model_name = item["model_feature_name"] if isinstance(item, dict) else item.model_feature_name
        original = item["original_feature_name"] if isinstance(item, dict) else item.original_feature_name
        display_name = FEATURE_DISPLAY_NAME_MAP.get(original)
        if display_name is None:
            missing.add(original)
            continue
        result.append(
            {"model_feature_name": model_name, "original_feature_name": original, "display_name": display_name}
        )
    if missing:
        raise ModelArtifactError(f"Display names are missing for: {sorted(missing)}")
    return result


def build_serving_metadata(
    bundle: ModelBundle,
    model_type: ModelType,
    train_set: str,
    algorithm: str,
    hyperparameters: dict[str, Any],
    calibration_method: str,
    source_model_sha256: str,
    training_data_sha256: dict[str, str],
    X_train: pd.DataFrame,
    test_metrics: dict[str, Any],
) -> dict[str, Any]:
    """재학습과 버전 추적에 필요한 정보입니다. 파일 해시(files)는 저장할 때 채웁니다."""
    input_schema = build_input_schema(bundle, X_train)
    return {
        "schema_version": SERVING_BUNDLE_SCHEMA_VERSION,
        "model_type": str(model_type),
        "train_set": train_set,
        "algorithm": algorithm,
        "hyperparameters": hyperparameters,
        "calibration_method": calibration_method,
        "source_model_sha256": source_model_sha256,
        "training_data_sha256": training_data_sha256,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_version": code_version(),
        "library_versions": library_versions(),
        "input_schema": input_schema,
        "numeric_ranges": build_numeric_ranges(X_train, input_schema["numeric"]),
        "test_metrics": test_metrics,
    }


def model_version(bundle: ModelBundle) -> str:
    meta = bundle.metadata or {}
    source = str(meta.get("source_model_sha256"))[:12]
    return f"{meta.get('model_type')}:{meta.get('train_set')}:{meta.get('algorithm')}:{source}"


def save_serving_artifacts(
    bundle: ModelBundle, model_dir: Path, threshold_criteria: dict[str, Any] | None = None
) -> Path:
    """
    번들을 역할별 파일로 나눠 저장하고, 각 파일의 해시를 metadata.json에 기록합니다.
    metadata.json 경로를 반환하며, 이 파일의 해시는 매니페스트에 기록합니다.
    """
    if not bundle.metadata:
        raise ModelArtifactError("Bundle has no serving metadata")
    if bundle.calibrator is None or not bundle.risk_thresholds:
        raise ModelArtifactError("Bundle must have a calibrator and risk thresholds")

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle.model, model_dir / SERVING_MODEL_FILE)
    joblib.dump(
        {"preprocessor": bundle.preprocessor, "post_preprocessor": bundle.post_preprocessor},
        model_dir / SERVING_PREPROCESSOR_FILE,
    )
    joblib.dump(bundle.calibrator, model_dir / SERVING_CALIBRATOR_FILE)
    thresholds = {
        "moderate": float(bundle.risk_thresholds["moderate"]),
        "high": float(bundle.risk_thresholds["high"]),
        "decision_threshold": float(bundle.threshold),
        "rule": "probability >= high -> HIGH, >= moderate -> MODERATE, otherwise LOW",
        "criteria": threshold_criteria or {},
    }
    _write_json(model_dir / SERVING_THRESHOLDS_FILE, thresholds)

    metadata = {
        **bundle.metadata,
        "feature_names": list(bundle.feature_names),
        "feature_metadata": list(bundle.feature_metadata or []),
        "files": {name: file_sha256(model_dir / name) for name in SERVING_HASHED_FILES},
    }
    metadata_path = model_dir / SERVING_METADATA_FILE
    _write_json(metadata_path, metadata)
    return metadata_path


def validate_serving_bundle(bundle: ModelBundle, model_type: ModelType) -> None:
    meta = bundle.metadata
    if not meta:
        raise ModelArtifactError(f"{model_type}: bundle has no serving metadata")
    missing = [key for key in SERVING_METADATA_REQUIRED_KEYS if key not in meta]
    if missing:
        raise ModelArtifactError(f"{model_type}: serving metadata is missing {missing}")
    if meta["schema_version"] != SERVING_BUNDLE_SCHEMA_VERSION:
        raise ModelArtifactError(f"{model_type}: unsupported bundle schema version {meta['schema_version']}")
    if meta["model_type"] != str(model_type):
        raise ModelArtifactError(f"{model_type}: bundle was built for {meta['model_type']}")
    if bundle.calibrator is None:
        raise ModelArtifactError(f"{model_type}: calibrator is missing")
    if not bundle.risk_thresholds or set(bundle.risk_thresholds) != RISK_THRESHOLD_KEYS:
        raise ModelArtifactError(f"{model_type}: risk thresholds are missing")
    columns = list(getattr(bundle.preprocessor, "feature_names_in_", []))
    if columns != meta["input_schema"]["columns"]:
        raise ModelArtifactError(f"{model_type}: input schema differs from the preprocessor")

    current = library_versions()
    changed = {
        name: (version, current.get(name))
        for name, version in meta["library_versions"].items()
        if version != current.get(name)
    }
    if changed:
        logger.warning("%s: library versions differ from the bundle (saved, current): %s", model_type, changed)


def read_manifest(serving_dir: Path) -> dict[str, Any]:
    path = serving_dir / SERVING_MANIFEST_NAME
    if not path.exists():
        raise ModelArtifactError(f"Serving manifest not found: {path}")
    return dict(json.loads(path.read_text(encoding="utf-8")))


def write_manifest(serving_dir: Path, manifest: dict[str, Any]) -> Path:
    path = serving_dir / SERVING_MANIFEST_NAME
    _write_json(path, manifest)
    return path


def manifest_entry(serving_dir: Path, model_type: ModelType, metadata_path: Path) -> dict[str, Any]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return {
        "directory": metadata_path.parent.relative_to(serving_dir).as_posix(),
        "metadata_sha256": file_sha256(metadata_path),
        "source_model_sha256": metadata["source_model_sha256"],
        "train_set": metadata["train_set"],
        "algorithm": metadata["algorithm"],
        "created_at": metadata["created_at"],
    }


def load_serving_bundle(serving_dir: Path, model_type: ModelType) -> ModelBundle:
    """
    매니페스트에 기록된 metadata.json 해시, metadata.json에 기록된 파일별 해시를 차례로 확인한 뒤
    파일들을 읽어 ModelBundle로 조립합니다.
    """
    manifest = read_manifest(serving_dir)
    entry = manifest.get(str(model_type))
    if entry is None:
        raise ModelArtifactError(f"{model_type}: not listed in the serving manifest")

    model_dir = serving_dir / str(entry.get("directory", serving_model_dirname(model_type)))
    metadata_path = model_dir / SERVING_METADATA_FILE
    if not metadata_path.exists():
        raise ModelArtifactError(f"{model_type}: metadata not found: {metadata_path}")
    if file_sha256(metadata_path) != entry.get("metadata_sha256"):
        raise ModelArtifactError(f"{model_type}: metadata hash does not match the manifest")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    expected_hashes = metadata.get("files", {})
    for name in SERVING_HASHED_FILES:
        path = model_dir / name
        if not path.exists():
            raise ModelArtifactError(f"{model_type}: artifact not found: {name}")
        if file_sha256(path) != expected_hashes.get(name):
            raise ModelArtifactError(f"{model_type}: {name} hash does not match the metadata")

    try:
        model = joblib.load(model_dir / SERVING_MODEL_FILE)
        preprocessors = joblib.load(model_dir / SERVING_PREPROCESSOR_FILE)
        calibrator = joblib.load(model_dir / SERVING_CALIBRATOR_FILE)
    except Exception as error:
        raise ModelArtifactError(f"{model_type}: failed to load artifacts: {type(error).__name__}") from error
    thresholds = json.loads((model_dir / SERVING_THRESHOLDS_FILE).read_text(encoding="utf-8"))

    bundle = ModelBundle(
        model=model,
        preprocessor=preprocessors["preprocessor"],
        post_preprocessor=preprocessors.get("post_preprocessor"),
        feature_names=list(metadata.get("feature_names", [])),
        threshold=float(thresholds["decision_threshold"]),
        feature_metadata=list(metadata.get("feature_metadata", [])),
        calibrator=calibrator,
        risk_thresholds={key: float(thresholds[key]) for key in RISK_THRESHOLD_KEYS},
        metadata=metadata,
    )
    validate_serving_bundle(bundle, model_type)
    return bundle


def _write_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
