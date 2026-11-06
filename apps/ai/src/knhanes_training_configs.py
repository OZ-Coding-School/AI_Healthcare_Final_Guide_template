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

# 혈액 지표가 모두 없는 행은 음성으로 확정할 수 없어 양성만 남습니다.
# 결측 여부가 라벨을 드러내므로 해당 질환의 학습과 평가에서 제외합니다.
BLOOD_INPUT_COLUMNS = ["총콜레스테롤", "HDL-콜레스테롤", "중성지방", "AST", "ALT", "혈중크레아티닌"]
BLOOD_MISSING_EXCLUDED_MODELS = [ModelType.DIABETES_RISK]

# 값이 코드 목록에 있으면 이미 진단·치료 중인 응답자입니다.
MODEL_DIAGNOSED_CODES_MAP: dict[ModelType, dict[str, list[int]]] = {
    ModelType.DIABETES_RISK: {"DE1_dg": [1], "DE1_31": [1], "DE1_32": [1]},
    ModelType.HYPERTENSION_RISK: {"DI1_pr": [1], "DI1_2": [1, 2, 3, 4]},
}

# Train A와 기준이 되는 비교 대상. 측정 체계가 같은 Train B를 먼저 비교합니다.
BASELINE_REFERENCE_TRAIN_SET = KnhanesTrainSet.TRAIN_A
BASELINE_COMPARED_TRAIN_SETS = [KnhanesTrainSet.TRAIN_B, KnhanesTrainSet.TRAIN_A_TG]
