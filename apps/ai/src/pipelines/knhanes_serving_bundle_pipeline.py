"""
10번에서 Test로 평가한 최종 번들을 서빙용 번들로 내보냅니다.

- 재학습하지 않습니다. 같은 모델 객체에 출처·입력 스키마·버전·표시명만 추가합니다.
- 최종 평가 보고서의 SHA-256과 원 번들 파일이 다르면 거부합니다(평가 후 바뀐 모델을 서빙하지 않음).
- 저장 후 다시 로드해 Validation 예측값이 원 번들과 완전히 같은지 확인합니다. Test는 읽지 않습니다.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.logger import configure_logger
from src.components.knhanes_inference_errors import ModelArtifactError
from src.components.knhanes_serving_bundle import (
    build_display_feature_metadata,
    build_serving_metadata,
    file_sha256,
    load_serving_bundle,
    write_manifest,
)
from src.components.model_trainer import ModelBundle
from src.enums import ModelType
from src.knhanes_inference_configs import SERVING_MODEL_DIR, serving_bundle_filename
from src.pipelines.knhanes_data_pipeline import SPLIT_DATA_DIR
from src.pipelines.knhanes_final_evaluation_pipeline import FINAL_EVALUATION_REPORT_DIR, FINAL_EVALUATION_REPORT_NAME
from src.pipelines.knhanes_tuning_pipeline import TUNING_MODEL_DIR

logger = configure_logger("KNHANES Serving Bundle")

TEST_METRIC_KEYS = ["rows", "positive_rate", "roc_auc", "pr_auc", "brier", "mean_predicted"]


def load_final_evaluation(report_path: Path) -> dict[str, dict[str, Any]]:
    if not report_path.exists():
        raise FileNotFoundError(f"Final evaluation report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    models = report.get("models", {})
    missing = [str(model_type) for model_type in ModelType if str(model_type) not in models]
    if missing:
        raise ModelArtifactError(f"Final evaluation report has no result for {missing}")
    return dict(models)


def resolve_source_model_path(recorded_path: str, model_dir: Path) -> Path:
    """보고서의 절대 경로가 없으면(다른 PC 등) 튜닝 모델 폴더에서 같은 파일명을 찾습니다."""
    path = Path(recorded_path)
    return path if path.exists() else model_dir / path.name


def summarize_test_metrics(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        group: {key: values[key] for key in TEST_METRIC_KEYS if key in values}
        for group, values in metrics.items()
        if isinstance(values, dict)
    }


def load_split_features(split_data_dir: Path, model_type: ModelType, train_set: str, name: str) -> pd.DataFrame:
    path = split_data_dir / str(model_type) / train_set / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"KNHANES split file not found: {path}")
    return pd.read_parquet(path)


@dataclass(frozen=True)
class ExportedBundle:
    manifest_entry: dict[str, Any]
    X_validation: pd.DataFrame
    source_validation_prob: np.ndarray


def export_serving_bundle(
    model_type: ModelType,
    evaluation: dict[str, Any],
    split_data_dir: Path,
    source_model_dir: Path,
    output_dir: Path,
) -> ExportedBundle:
    source_path = resolve_source_model_path(evaluation["model_path"], source_model_dir)
    if not source_path.exists():
        raise ModelArtifactError(f"{model_type}: source model not found: {source_path}")
    source_sha256 = file_sha256(source_path)
    if source_sha256 != evaluation["model_sha256"]:
        raise ModelArtifactError(f"{model_type}: source model differs from the one evaluated on Test")

    bundle = ModelBundle.load(source_path)
    train_set = str(evaluation["train_set"])
    X_train = load_split_features(split_data_dir, model_type, train_set, "X_train")
    X_validation = load_split_features(split_data_dir, model_type, train_set, "X_validation")
    # 메타데이터를 붙이기 전 원 번들의 예측값입니다. 서빙 번들과의 일치 확인에 씁니다.
    source_validation_prob = bundle.predict_proba(X_validation)

    bundle.feature_metadata = build_display_feature_metadata(bundle)
    bundle.metadata = build_serving_metadata(
        bundle=bundle,
        model_type=model_type,
        train_set=train_set,
        algorithm=str(evaluation["algorithm"]),
        source_model_sha256=source_sha256,
        X_train=X_train,
        test_metrics=summarize_test_metrics(evaluation["metrics"]),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / serving_bundle_filename(model_type)
    bundle.save(output_path)
    manifest_entry = {
        "file": output_path.name,
        "sha256": file_sha256(output_path),
        "source_model_sha256": source_sha256,
        "train_set": train_set,
        "algorithm": bundle.metadata["algorithm"],
        "created_at": bundle.metadata["created_at"],
    }
    return ExportedBundle(manifest_entry, X_validation, source_validation_prob)


def run_knhanes_serving_bundle_export(
    final_report_path: Path = FINAL_EVALUATION_REPORT_DIR / FINAL_EVALUATION_REPORT_NAME,
    split_data_dir: Path = SPLIT_DATA_DIR,
    source_model_dir: Path = TUNING_MODEL_DIR,
    output_dir: Path = SERVING_MODEL_DIR,
) -> dict[str, Any]:
    evaluations = load_final_evaluation(final_report_path)

    exported = {
        model_type: export_serving_bundle(
            model_type, evaluations[str(model_type)], split_data_dir, source_model_dir, output_dir
        )
        for model_type in ModelType
    }
    manifest = {str(model_type): item.manifest_entry for model_type, item in exported.items()}
    write_manifest(output_dir, manifest)

    # 매니페스트 해시로 다시 로드해 원 번들과 예측값이 완전히 같은지 확인합니다.
    for model_type, item in exported.items():
        serving_prob = load_serving_bundle(output_dir, model_type).predict_proba(item.X_validation)
        if not np.array_equal(item.source_validation_prob, serving_prob):
            raise ModelArtifactError(f"{model_type}: serving bundle predictions differ from the source bundle")
        logger.info(f"{model_type}: serving bundle exported ({len(item.X_validation)} validation rows identical)")

    return manifest


if __name__ == "__main__":
    run_knhanes_serving_bundle_export()
