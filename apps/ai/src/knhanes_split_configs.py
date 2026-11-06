# knhanes 검사값 전환·데이터 분할 상수
from dataclasses import dataclass

from src.enums import KnhanesTrainSet

# 측정 체계가 다른 연도: Train A에만 포함
KNHANES_EARLY_TRAIN_YEARS = [2020, 2021]

# 2022년 검사기관 변경 후 연도: 가구 단위로 Train과 Validation을 나눔
KNHANES_DEVELOPMENT_YEARS = [2022, 2023]

# 최종 평가 연도
KNHANES_TEST_YEARS = [2024]

# 개발 연도를 이 수로 나눈 가구 묶음 중 하나를 Validation으로 사용
KNHANES_VALIDATION_FOLDS = 4

# 분할 시드: 바꾸면 Train과 Validation 구성원이 달라짐
KNHANES_SPLIT_RANDOM_STATE = 42


@dataclass(frozen=True)
class LabHarmonizationRule:
    """제8·9기 이용지침서의 검사값 전환식: y = slope * x + intercept"""

    var_name: str
    years: tuple[int, ...]
    slope: float
    intercept: float


# 2022년 이후 값을 2021년 이전 기준으로 전환
HBA1C_RULE = LabHarmonizationRule("HE_HbA1c", (2022, 2023, 2024), 1.034, -0.0448)
AST_RULE = LabHarmonizationRule("HE_ast", (2022, 2023, 2024), 1.057, 1.8490)
ALT_RULE = LabHarmonizationRule("HE_alt", (2022, 2023, 2024), 1.091, -0.6364)

# 2021년 이전 값을 2022년 이후 기준으로 전환
TRIGLYCERIDE_RULE = LabHarmonizationRule("HE_TG", (2020, 2021), 0.99, 11.94)

# 학습 구성별 전환식: Validation과 Test에도 같은 전환식을 적용
KNHANES_TRAIN_SET_RULES_MAP = {
    KnhanesTrainSet.TRAIN_A: [HBA1C_RULE, AST_RULE, ALT_RULE],
    KnhanesTrainSet.TRAIN_A_TG: [HBA1C_RULE, AST_RULE, ALT_RULE, TRIGLYCERIDE_RULE],
    KnhanesTrainSet.TRAIN_B: [],
}

# 2020~2021년 데이터를 학습에 쓰는 구성
KNHANES_EARLY_YEAR_TRAIN_SETS = [KnhanesTrainSet.TRAIN_A, KnhanesTrainSet.TRAIN_A_TG]
