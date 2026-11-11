"""
서비스 입력을 KNHANES 원시 코드로 변환합니다.

변환 결과는 학습 데이터와 같은 KnhanesPreprocessor.preprocess()를 거치므로,
코드값 정제·파생변수 규칙을 이 파일에서 다시 구현하지 않습니다. 이 파일은 코드 체계만 맞춥니다.
"""

import numpy as np
import pandas as pd

from src.components.knhanes_service_input import (
    FamilyHistoryAnswer,
    FamilyHistoryInput,
    ServiceDrinkingFrequency,
    ServiceGender,
    ServiceHabitStatus,
    ServiceHealthInput,
    ServiceUrinalysisStatus,
)
from src.knhanes_inference_configs import (
    DRINKS_PER_SESSION_CODE_BINS,
    DRINKS_PER_SESSION_MAX_CODE,
    KNHANES_AGE_TOP_CODE,
)

SEX_CODE_MAP = {ServiceGender.MALE: 1, ServiceGender.FEMALE: 2}

# DE1_pr·DI1_pr: 1 있음, 0 없음 (전처리에서 0·8 모두 N)
DISEASE_STATUS_CODE_MAP = {True: 1, False: 0}

# BD1 평생음주경험: 1 마셔 본 적 없음, 2 있음
LIFETIME_DRINKING_CODE_MAP = {
    ServiceHabitStatus.NEVER: 1,
    ServiceHabitStatus.FORMER: 2,
    ServiceHabitStatus.CURRENT: 2,
}

# BD1_11 1년간 음주빈도: 현재 음주자만 빈도 코드 사용
DRINKING_FREQUENCY_CODE_MAP = {
    ServiceDrinkingFrequency.LESS_THAN_MONTHLY: 2,
    ServiceDrinkingFrequency.MONTHLY: 3,
    ServiceDrinkingFrequency.MONTHLY_2_TO_4: 4,
    ServiceDrinkingFrequency.WEEKLY_2_TO_3: 5,
    ServiceDrinkingFrequency.WEEKLY_4_OR_MORE: 6,
}
NEVER_DRANK_FREQUENCY_CODE = 8  # 비해당: 평생 마셔 본 적 없음
NO_DRINK_LAST_YEAR_FREQUENCY_CODE = 1  # 최근 1년간 전혀 마시지 않음

DRINKS_NOT_APPLICABLE_CODE = 8  # 비해당: 최근 1년간 마시지 않음
DRINKS_UNKNOWN_CODE = 9  # 모름 → 전처리에서 결측

# BS3_1 현재 흡연 여부: 1 매일, 2 가끔(모두 CURRENT), 3 과거 흡연, 8 비해당
SMOKING_STATUS_CODE_MAP = {
    ServiceHabitStatus.NEVER: 8,
    ServiceHabitStatus.FORMER: 3,
    ServiceHabitStatus.CURRENT: 1,
}
CIGARETTES_NOT_APPLICABLE_CODE = 888  # 비흡연 → 전처리에서 0개비
CIGARETTES_UNKNOWN_CODE = 999  # 모름 → 전처리에서 결측

URINALYSIS_CODE_MAP = {
    ServiceUrinalysisStatus.NEGATIVE: 0,
    ServiceUrinalysisStatus.TRACE: 1,
    ServiceUrinalysisStatus.POSITIVE_1: 2,
    ServiceUrinalysisStatus.POSITIVE_2: 3,
    ServiceUrinalysisStatus.POSITIVE_3: 4,
    ServiceUrinalysisStatus.POSITIVE_4: 5,
}

FAMILY_HISTORY_CODE_MAP = {
    FamilyHistoryAnswer.NO: 0,
    FamilyHistoryAnswer.YES: 1,
    FamilyHistoryAnswer.NO_SIBLINGS: 8,
    FamilyHistoryAnswer.UNKNOWN: 9,
}


def drinks_per_session_code(drinks: int) -> int:
    """회당 잔 수를 KNHANES BD2_1 구간 코드로 바꿉니다."""
    if drinks < 1:
        raise ValueError("drinks must be at least 1")
    for upper, code in DRINKS_PER_SESSION_CODE_BINS:
        if drinks <= upper:
            return code
    return DRINKS_PER_SESSION_MAX_CODE


def to_knhanes_raw_frame(service_input: ServiceHealthInput) -> pd.DataFrame:
    """
    서비스 입력 1건을 두 모델의 입력 변수를 모두 담은 KNHANES 원시 코드 1행으로 변환합니다.
    BMI는 비워 두고 전처리에서 키·체중으로 계산합니다(학습 데이터와 같은 계산식).
    """
    row: dict[str, float] = {
        "sex": SEX_CODE_MAP[service_input.gender],
        "age": min(service_input.age, KNHANES_AGE_TOP_CODE),
        "HE_ht": service_input.height,
        "HE_wt": service_input.weight,
        "HE_wc": service_input.waist_circumference,
        "HE_BMI": np.nan,
        "HE_sbp": service_input.sbp,
        "HE_dbp": service_input.dbp,
        "HE_glu": service_input.fbs,
        "HE_HbA1c": service_input.hba1c,
        "HE_chol": service_input.total_cholesterol,
        "HE_HDL_st2": service_input.hdl,
        "HE_TG": service_input.triglyceride,
        "HE_ast": service_input.ast,
        "HE_alt": service_input.alt,
        "HE_crea": service_input.creatinine,
        "HE_Upro": URINALYSIS_CODE_MAP[service_input.urine_protein],
        "HE_Uglu": URINALYSIS_CODE_MAP[service_input.urine_glucose],
        "DE1_pr": DISEASE_STATUS_CODE_MAP[service_input.has_diabetes],
        "DI1_pr": DISEASE_STATUS_CODE_MAP[service_input.has_hypertension],
        **_smoking_codes(service_input),
        **_drinking_codes(service_input),
        **_family_history_codes("HE_DMfh", service_input.diabetes_family_history),
        **_family_history_codes("HE_HPfh", service_input.hypertension_family_history),
    }
    return pd.DataFrame([row]).astype(float)


def _smoking_codes(service_input: ServiceHealthInput) -> dict[str, float]:
    status = service_input.smoking_status
    if status != ServiceHabitStatus.CURRENT:
        amount = CIGARETTES_NOT_APPLICABLE_CODE
    elif service_input.cigarettes_per_day is None:
        amount = CIGARETTES_UNKNOWN_CODE
    else:
        amount = service_input.cigarettes_per_day
    return {"BS3_1": SMOKING_STATUS_CODE_MAP[status], "BS3_2": amount}


def _drinking_codes(service_input: ServiceHealthInput) -> dict[str, float]:
    status = service_input.drinking_status
    if status == ServiceHabitStatus.NEVER:
        frequency = NEVER_DRANK_FREQUENCY_CODE
        amount = DRINKS_NOT_APPLICABLE_CODE
    elif status == ServiceHabitStatus.FORMER:
        frequency = NO_DRINK_LAST_YEAR_FREQUENCY_CODE
        amount = DRINKS_NOT_APPLICABLE_CODE
    else:
        frequency = DRINKING_FREQUENCY_CODE_MAP[service_input.drinking_frequency]
        drinks = service_input.drinks_per_session
        amount = DRINKS_UNKNOWN_CODE if drinks is None else drinks_per_session_code(drinks)
    return {"BD1": LIFETIME_DRINKING_CODE_MAP[status], "BD1_11": frequency, "BD2_1": amount}


def _family_history_codes(prefix: str, family_history: FamilyHistoryInput) -> dict[str, float]:
    return {
        f"{prefix}1": FAMILY_HISTORY_CODE_MAP[family_history.father],
        f"{prefix}2": FAMILY_HISTORY_CODE_MAP[family_history.mother],
        f"{prefix}3": FAMILY_HISTORY_CODE_MAP[family_history.siblings],
    }
