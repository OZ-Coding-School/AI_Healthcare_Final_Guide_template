"""
서빙 아티팩트가 학습 코드로 다시 만들어지는지 확인합니다.

metadata.json에 기록된 학습 데이터 해시, 하이퍼파라미터, 보정 방법으로 처음부터 다시 학습해 다음을 비교합니다.
Test는 읽지 않습니다.

1. 학습 데이터(X_train, y_train) 해시가 아티팩트 생성 때와 같은지
2. 같은 하이퍼파라미터로 학습한 모델의 Validation 원 확률이 같은지
3. Train OOF로 다시 고른 보정 방법과 보정 확률이 같은지
4. 미진단자 Validation으로 다시 산출한 위험 등급 경계가 같은지

Optuna 탐색 자체는 다시 실행하지 않습니다(수십 분 소요). 탐색 결과인 하이퍼파라미터는 metadata.json에 기록되어 있습니다.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from core.config import settings
from core.logger import configure_logger
from src.components.knhanes_hyperparameter_tuner import cross_validate_oof, make_household_folds
from src.components.knhanes_inference_errors import ModelArtifactError
from src.components.knhanes_probability_calibrator import select_calibrator
from src.components.knhanes_risk_threshold import find_risk_thresholds
from src.components.knhanes_serving_bundle import file_sha256, load_serving_bundle
from src.components.model_trainer import BinaryClassificationModelTrainer
from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType
from src.knhanes_inference_configs import SERVING_MODEL_DIR, SERVING_THRESHOLDS_FILE, serving_model_dirname
from src.knhanes_tuning_configs import TUNING_N_FOLDS, TUNING_RANDOM_STATE
from src.pipelines.knhanes_data_pipeline import LABELED_DATA_DIR, SPLIT_DATA_DIR
from src.pipelines.knhanes_training_pipeline import ID_VAR, load_diagnosed_flags
from src.pipelines.knhanes_tuning_pipeline import load_tuning_dataset

logger = configure_logger("KNHANES Reproducibility")

REPRODUCIBILITY_REPORT_DIR = settings.MODEL_REPORT_DIR / "knhanes_reproducibility"


def check_model_reproducibility(
    model_type: ModelType,
    serving_dir: Path,
    split_data_dir: Path,
    labeled_data_dir: Path,
    n_folds: int = TUNING_N_FOLDS,
    fold_n_jobs: int = 1,
) -> dict[str, Any]:
    bundle = load_serving_bundle(serving_dir, model_type)
    meta = bundle.metadata or {}
    train_set = KnhanesTrainSet(meta["train_set"])
    split_dir = split_data_dir / str(model_type) / str(train_set)

    data_hashes = {name: file_sha256(split_dir / f"{name}.parquet") for name in meta["training_data_sha256"]}
    data_identical = data_hashes == meta["training_data_sha256"]

    dataset = load_tuning_dataset(split_data_dir, model_type, train_set)
    algorithm = ModelAlgorithm(meta["algorithm"])
    retrained = BinaryClassificationModelTrainer(
        x_train=dataset.X_train,
        y_train=dataset.y_train,
        algorithm=algorithm,
        random_state=TUNING_RANDOM_STATE,
        hyperparameters=dict(meta["hyperparameters"]),
    ).train()

    saved_raw = np.asarray(bundle.model.predict_proba(bundle.transform(dataset.X_validation)))[:, 1]
    retrained_raw = np.asarray(retrained.model.predict_proba(retrained.transform(dataset.X_validation)))[:, 1]

    folds = make_household_folds(dataset.y_train, dataset.households_train, n_folds, TUNING_RANDOM_STATE)
    oof_prob = cross_validate_oof(
        dataset.X_train,
        dataset.y_train,
        folds,
        algorithm,
        dict(meta["hyperparameters"]),
        TUNING_RANDOM_STATE,
        fold_n_jobs,
    )
    calibrator, _ = select_calibrator(oof_prob, dataset.y_train, folds)
    retrained.calibrator = calibrator
    saved_prob = bundle.predict_proba(dataset.X_validation)
    retrained_prob = retrained.predict_proba(dataset.X_validation)

    thresholds_path = serving_dir / serving_model_dirname(model_type) / SERVING_THRESHOLDS_FILE
    criteria = json.loads(thresholds_path.read_text(encoding="utf-8"))["criteria"]
    diagnosed = load_diagnosed_flags(labeled_data_dir, model_type, dataset.meta_validation[ID_VAR]).to_numpy()
    mask = ~diagnosed if criteria.get("group") == "undiagnosed" else np.ones(len(diagnosed), dtype=bool)
    recomputed = find_risk_thresholds(
        dataset.y_validation[mask], retrained_prob[mask], criteria["min_recall"], criteria["min_specificity"]
    ).to_dict()

    checks = {
        "training_data_identical": data_identical,
        "model_predictions_identical": bool(np.array_equal(saved_raw, retrained_raw)),
        "calibration_method_identical": calibrator.method == meta["calibration_method"],
        "calibrated_predictions_identical": bool(np.array_equal(saved_prob, retrained_prob)),
        "risk_thresholds_identical": recomputed == bundle.risk_thresholds,
    }
    return {
        "train_set": str(train_set),
        "algorithm": str(algorithm),
        "validation_rows": int(len(dataset.X_validation)),
        "max_abs_probability_diff": float(np.max(np.abs(saved_prob - retrained_prob))),
        "recomputed_risk_thresholds": recomputed,
        "saved_risk_thresholds": bundle.risk_thresholds,
        "checks": checks,
        "reproduced": all(checks.values()),
    }


def run_knhanes_reproducibility_check(
    serving_dir: Path = SERVING_MODEL_DIR,
    split_data_dir: Path = SPLIT_DATA_DIR,
    labeled_data_dir: Path = LABELED_DATA_DIR,
    report_dir: Path = REPRODUCIBILITY_REPORT_DIR,
    fold_n_jobs: int = 1,
) -> dict[str, Any]:
    results = {
        str(model_type): check_model_reproducibility(
            model_type, serving_dir, split_data_dir, labeled_data_dir, fold_n_jobs=fold_n_jobs
        )
        for model_type in ModelType
    }
    report = {"test_split_used": False, "models": results}

    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "reproducibility_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for model_type, result in results.items():
        logger.info(f"{model_type}: reproduced={result['reproduced']} checks={result['checks']}")

    failed = [model_type for model_type, result in results.items() if not result["reproduced"]]
    if failed:
        raise ModelArtifactError(f"Serving artifacts could not be reproduced for {failed}")
    return report


if __name__ == "__main__":
    run_knhanes_reproducibility_check()
