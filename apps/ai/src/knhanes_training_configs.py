# knhanes Baseline 학습 상수
from typing import Any

from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType

BASELINE_RANDOM_STATE = 42

# Baseline은 기본 파라미터로 비교합니다. 튜닝은 Optuna 단계에서 수행합니다.
BASELINE_ALGORITHMS = list(ModelAlgorithm)
BASELINE_RESAMPLING_OPTIONS = [False, True]
BASELINE_HYPERPARAMETERS_MAP: dict[ModelAlgorithm, dict[str, Any]] = {
    ModelAlgorithm.LOGISTIC_REGRESSION: {"max_iter": 2000},
    ModelAlgorithm.RANDOM_FOREST: {"n_jobs": -1},
    ModelAlgorithm.XGBOOST: {"n_jobs": -1},
    ModelAlgorithm.LIGHTGBM: {"n_jobs": -1, "verbose": -1},
    ModelAlgorithm.GRADIENT_BOOSTING: {},
}

# 가구 단위 부트스트랩 반복 수: 같은 가구의 예측은 서로 독립이 아닙니다.
BASELINE_BOOTSTRAP_ITERATIONS = 1000
BASELINE_CONFIDENCE_LEVEL = 0.95

# 값이 코드 목록에 있으면 이미 진단·치료 중인 응답자입니다.
MODEL_DIAGNOSED_CODES_MAP: dict[ModelType, dict[str, list[int]]] = {
    ModelType.DIABETES_RISK: {"DE1_dg": [1], "DE1_31": [1], "DE1_32": [1]},
    ModelType.HYPERTENSION_RISK: {"DI1_pr": [1], "DI1_2": [1, 2, 3, 4]},
}

# Train A와 기준이 되는 비교 대상. 측정 체계가 같은 Train B를 먼저 비교합니다.
BASELINE_REFERENCE_TRAIN_SET = KnhanesTrainSet.TRAIN_A
BASELINE_COMPARED_TRAIN_SETS = [KnhanesTrainSet.TRAIN_B, KnhanesTrainSet.TRAIN_A_TG]
