# knhanes 튜닝·확률 보정·위험 등급 임계값 상수
from dataclasses import dataclass
from typing import Any

from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType


@dataclass(frozen=True)
class IntParam:
    low: int
    high: int
    log: bool = False


@dataclass(frozen=True)
class FloatParam:
    low: float
    high: float
    log: bool = False


@dataclass(frozen=True)
class CategoricalParam:
    choices: tuple[Any, ...]


SearchParam = IntParam | FloatParam | CategoricalParam

TUNING_RANDOM_STATE = 42

# 튜닝은 Train 안에서 가구(ID_fam) 단위 교차검증으로만 수행합니다. Validation은 확인과 임계값 산출에만 씁니다.
TUNING_N_FOLDS = 5
TUNING_N_TRIALS = 100
# 알고리즘별 Study 실행 시간 상한(초). 상한에 걸리면 완료된 trial 수가 보고서에 남습니다.
TUNING_TIMEOUT_SECONDS = 1800
# 폴드를 병렬로 학습합니다. LightGBM은 폴드당 스레드 수를 고정해 과도한 병렬화를 막습니다.
TUNING_FOLD_N_JOBS = 5

# CV PR-AUC 차이가 이 값 이하인 후보 중에서는 Log loss가 낮은 쪽을 고릅니다.
TUNING_PR_AUC_TIE_TOLERANCE = 0.002

# 8번 Baseline 결과에서 상위였던 알고리즘만 튜닝합니다. SMOTE와 클래스 가중치는 확률을 왜곡해 제외합니다.
TUNING_CANDIDATE_ALGORITHMS_MAP: dict[ModelType, list[ModelAlgorithm]] = {
    ModelType.DIABETES_RISK: [ModelAlgorithm.LIGHTGBM, ModelAlgorithm.GRADIENT_BOOSTING],
    ModelType.HYPERTENSION_RISK: [
        ModelAlgorithm.GRADIENT_BOOSTING,
        ModelAlgorithm.LIGHTGBM,
        ModelAlgorithm.LOGISTIC_REGRESSION,
    ],
}

# 튜닝 중에도 바뀌지 않는 파라미터. Baseline 파라미터 위에 덮어씁니다.
TUNING_FIXED_HYPERPARAMETERS_MAP: dict[ModelAlgorithm, dict[str, Any]] = {
    ModelAlgorithm.LOGISTIC_REGRESSION: {"max_iter": 2000},
    ModelAlgorithm.LIGHTGBM: {"n_jobs": 2, "verbose": -1, "subsample_freq": 1, "deterministic": True},
    ModelAlgorithm.GRADIENT_BOOSTING: {},
}

TUNING_SEARCH_SPACES: dict[ModelAlgorithm, dict[str, SearchParam]] = {
    ModelAlgorithm.LIGHTGBM: {
        "n_estimators": IntParam(100, 1000, log=True),
        "learning_rate": FloatParam(0.01, 0.2, log=True),
        "num_leaves": IntParam(8, 128, log=True),
        "min_child_samples": IntParam(10, 200, log=True),
        "subsample": FloatParam(0.5, 1.0),
        "colsample_bytree": FloatParam(0.5, 1.0),
        "reg_lambda": FloatParam(1e-3, 10.0, log=True),
        "reg_alpha": FloatParam(1e-3, 10.0, log=True),
    },
    ModelAlgorithm.GRADIENT_BOOSTING: {
        "n_estimators": IntParam(50, 400, log=True),
        "learning_rate": FloatParam(0.01, 0.2, log=True),
        "max_depth": IntParam(2, 5),
        "min_samples_leaf": IntParam(5, 100, log=True),
        "subsample": FloatParam(0.6, 1.0),
        "max_features": CategoricalParam((None, "sqrt")),
    },
    ModelAlgorithm.LOGISTIC_REGRESSION: {
        "C": FloatParam(1e-3, 100.0, log=True),
    },
}

# 당뇨는 미진단자 Validation 기준으로 학습 구성을 다시 비교합니다. 고혈압은 8번 결론(Train B)을 유지합니다.
TUNING_TRAIN_SET_COMPARISON_ALGORITHM_MAP: dict[ModelType, ModelAlgorithm] = {
    ModelType.DIABETES_RISK: ModelAlgorithm.LIGHTGBM,
}
TUNING_DEFAULT_TRAIN_SET_MAP: dict[ModelType, KnhanesTrainSet] = {
    ModelType.DIABETES_RISK: KnhanesTrainSet.TRAIN_B,
    ModelType.HYPERTENSION_RISK: KnhanesTrainSet.TRAIN_B,
}

# 확률 보정 후보. none은 보정하지 않은 확률입니다.
CALIBRATION_METHODS = ["none", "sigmoid", "isotonic"]
# 보정 확률이 정확히 0이나 1이 되지 않도록 자릅니다.
CALIBRATION_PROBABILITY_EPSILON = 1e-4
CALIBRATION_ECE_BINS = 10

# 위험 등급 경계: MODERATE 이상은 재현율, HIGH는 특이도를 보장합니다. 미진단자 Validation 기준입니다.
RISK_MIN_RECALL = 0.90
RISK_MIN_SPECIFICITY = 0.90
RISK_THRESHOLD_GROUP = "undiagnosed"

TUNING_BOOTSTRAP_ITERATIONS = 1000
TUNING_CONFIDENCE_LEVEL = 0.95
