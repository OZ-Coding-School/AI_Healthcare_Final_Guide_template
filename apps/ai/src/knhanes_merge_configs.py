# knhanes 다년도 병합·검증 상수
from src.knhanes_preprocessing_configs import (
    IDENTIFIER_VARS,
    MODEL_INPUT_VARS_MAP,
    MODEL_LABEL_SOURCE_VARS_MAP,
    MODEL_OFFICIAL_LABEL_VAR_MAP,
    MODEL_TARGET_VAR_MAP,
    PREGNANCY_EXCLUSION_VARS,
    SURVEY_DESIGN_VARS,
)

# 다년도 병합 대상 연도: 2015~2019년은 보류
KNHANES_SURVEY_YEARS = [2020, 2021, 2022, 2023, 2024]

# 연도별 원시 파일명 형식: hn20_all.sas7bdat
KNHANES_RAW_FILE_TEMPLATE = "hn{yy}_all.sas7bdat"

# 학습 대상 최소 나이
KNHANES_ADULT_MIN_AGE = 19

# 다년도 병합 시 연도별 파일에 반드시 있어야 하는 변수
KNHANES_REQUIRED_VARS = list(
    dict.fromkeys(
        [
            *IDENTIFIER_VARS,
            *SURVEY_DESIGN_VARS,
            *PREGNANCY_EXCLUSION_VARS,
            *MODEL_OFFICIAL_LABEL_VAR_MAP.values(),
            *MODEL_TARGET_VAR_MAP.values(),
            *(var_name for var_names in MODEL_LABEL_SOURCE_VARS_MAP.values() for var_name in var_names),
            *(var_name for var_names in MODEL_INPUT_VARS_MAP.values() for var_name in var_names),
        ]
    )
)

# HE_HP의 고혈압 코드: 2020~2021년 3, 2022년부터 4
HE_HP_HYPERTENSION_CODE_BY_YEAR = {2020: 3, 2021: 3, 2022: 4, 2023: 4, 2024: 4}

_DISEASE_STATUS_CODES = {0, 1, 8, 9}
_PARENT_FAMILY_HISTORY_CODES = {0, 1, 9}
_SIBLING_FAMILY_HISTORY_CODES = {0, 1, 8, 9}
_URINALYSIS_CODES = {0, 1, 2, 3, 4, 5}

# 범주형 변수의 허용 코드: 결측은 검사하지 않음
KNHANES_EXPECTED_CODES_MAP: dict[str, set[int]] = {
    "sex": {1, 2},
    "DE1_dg": _DISEASE_STATUS_CODES,
    "DE1_pr": _DISEASE_STATUS_CODES,
    "DE1_31": _DISEASE_STATUS_CODES,
    "DE1_32": _DISEASE_STATUS_CODES,
    "DI1_pr": _DISEASE_STATUS_CODES,
    "DI1_2": {1, 2, 3, 4, 5, 8, 9},
    "HE_DM_HbA1c": {1, 2, 3},
    "BD1": {1, 2, 8, 9},
    "BD1_11": {1, 2, 3, 4, 5, 6, 8, 9},
    "BD2_1": {1, 2, 3, 4, 5, 8, 9},
    "BS3_1": {1, 2, 3, 8, 9},
    "HE_HPfh1": _PARENT_FAMILY_HISTORY_CODES,
    "HE_HPfh2": _PARENT_FAMILY_HISTORY_CODES,
    "HE_HPfh3": _SIBLING_FAMILY_HISTORY_CODES,
    "HE_DMfh1": _PARENT_FAMILY_HISTORY_CODES,
    "HE_DMfh2": _PARENT_FAMILY_HISTORY_CODES,
    "HE_DMfh3": _SIBLING_FAMILY_HISTORY_CODES,
    "HE_Upro": _URINALYSIS_CODES,
    "HE_Uglu": _URINALYSIS_CODES,
}
