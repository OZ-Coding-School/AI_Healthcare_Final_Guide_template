"""
서빙 번들의 메타데이터 생성, 무결성 확인, 로드를 담당합니다.

서빙 번들은 10번에서 Test로 평가한 번들과 같은 모델 객체를 그대로 담고, 출처·입력 스키마·버전만 추가합니다.
pickle은 로드 시 코드를 실행할 수 있으므로, 매니페스트에 기록한 SHA-256과 일치하는 파일만 로드합니다.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import pandas as pd

from src.components.knhanes_inference_errors import ModelArtifactError
from src.components.model_trainer import ModelBundle
from src.enums import ModelType
from src.knhanes_inference_configs import (
    FEATURE_DISPLAY_NAME_MAP,
    SERVING_BUNDLE_SCHEMA_VERSION,
    SERVING_MANIFEST_NAME,
    SERVING_METADATA_REQUIRED_KEYS,
    SERVING_TRACKED_LIBRARIES,
    serving_bundle_filename,
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
    source_model_sha256: str,
    X_train: pd.DataFrame,
    test_metrics: dict[str, Any],
) -> dict[str, Any]:
    input_schema = build_input_schema(bundle, X_train)
    return {
        "schema_version": SERVING_BUNDLE_SCHEMA_VERSION,
        "model_type": str(model_type),
        "train_set": train_set,
        "algorithm": algorithm,
        "source_model_sha256": source_model_sha256,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "library_versions": library_versions(),
        "input_schema": input_schema,
        "numeric_ranges": build_numeric_ranges(X_train, input_schema["numeric"]),
        "test_metrics": test_metrics,
    }


def model_version(bundle: ModelBundle) -> str:
    meta = bundle.metadata or {}
    return f"{meta.get('model_type')}:{meta.get('train_set')}:{meta.get('algorithm')}:{str(meta.get('source_model_sha256'))[:12]}"


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


def read_manifest(model_dir: Path) -> dict[str, Any]:
    path = model_dir / SERVING_MANIFEST_NAME
    if not path.exists():
        raise ModelArtifactError(f"Serving manifest not found: {path}")
    return dict(json.loads(path.read_text(encoding="utf-8")))


def write_manifest(model_dir: Path, manifest: dict[str, Any]) -> Path:
    path = model_dir / SERVING_MANIFEST_NAME
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_serving_bundle(model_dir: Path, model_type: ModelType) -> ModelBundle:
    """매니페스트의 해시와 일치하는 서빙 번들만 로드하고 메타데이터를 검증합니다."""
    manifest = read_manifest(model_dir)
    entry = manifest.get(str(model_type))
    if entry is None:
        raise ModelArtifactError(f"{model_type}: not listed in the serving manifest")

    path = model_dir / serving_bundle_filename(model_type)
    if not path.exists():
        raise ModelArtifactError(f"{model_type}: serving bundle not found: {path}")
    if file_sha256(path) != entry.get("sha256"):
        raise ModelArtifactError(f"{model_type}: serving bundle hash does not match the manifest")

    try:
        bundle = ModelBundle.load(path)
    except Exception as error:
        raise ModelArtifactError(f"{model_type}: failed to load serving bundle: {type(error).__name__}") from error
    validate_serving_bundle(bundle, model_type)
    return bundle
