from enum import StrEnum


class SmokingStatus(StrEnum):
    NEVER = "NEVER"
    FORMER = "FORMER"
    CURRENT = "CURRENT"


class LifetimeDrinkingExperience(StrEnum):
    Y = "Y"
    N = "N"


class DrinkingFrequency(StrEnum):
    NEVER = "NEVER"  # 마신적 없음
    LESS_THAN_MONTHLY = "LESS_THAN_MONTHLY"  # 월 1회 미만
    MONTHLY = "MONTHLY"  # 월 1회 정도
    MONTHLY_2_TO_4 = "MONTHLY_2_TO_4"  # 월 2~4회
    WEEKLY_2_TO_3 = "WEEKLY_2_TO_3"  # 주 2~3회
    WEEKLY_4_OR_MORE = "WEEKLY_4_OR_MORE"  # 주 4회 이상


class DrinkingAmount(StrEnum):
    ZERO = "0"
    ONE_TO_TWO = "1~2잔"
    THREE_TO_FOUR = "3~4잔"
    FIVE_TO_SIX = "5~6잔"
    SEVEN_TO_NINE = "7~9잔"
    MORE_THAN_10 = "10잔 이상"


class UrinalysisStatus(StrEnum):
    NEGATIVE = "-"
    TRACE = "±"
    POSITIVE_1 = "1+"
    POSITIVE_2 = "2+"
    POSITIVE_3 = "3+"
    POSITIVE_4 = "4+"


class ModelType(StrEnum):
    DIABETES_RISK = "diabetes_risk"
    HYPERTENSION_RISK = "hypertension_risk"


class KnhanesTrainSet(StrEnum):
    TRAIN_A = "train_a"  # 2020~2023년, HbA1c·AST·ALT 전환
    TRAIN_A_TG = "train_a_tg"  # Train A에 중성지방 전환 추가
    TRAIN_B = "train_b"  # 2022~2023년, 전환 없음


class ModelAlgorithm(StrEnum):
    RANDOM_FOREST = "RandomForest"
    XGBOOST = "XGBoost"
    LOGISTIC_REGRESSION = "LogisticRegression"
    LIGHTGBM = "LightGBM"
    GRADIENT_BOOSTING = "GradientBoosting"
