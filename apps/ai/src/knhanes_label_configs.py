# knhanes B안 라벨 생성 상수
from src.enums import ModelType

# 라벨 생성 결과 컬럼
DISEASE_LABEL_VAR = "disease_label"

# 이 시간 미만으로 공복한 측정값은 공복혈당으로 사용하지 않음
FASTING_MIN_HOURS = 8

# 양성 판정 기준값: 값 이상이면 양성
DIABETES_FASTING_GLUCOSE_MIN = 126
DIABETES_HBA1C_MIN = 6.5
HYPERTENSION_SYSTOLIC_MIN = 140
HYPERTENSION_DIASTOLIC_MIN = 90

# DI1_2의 혈압조절제 복용 코드: 5는 미복용
HYPERTENSION_MEDICATION_CODES = [1, 2, 3, 4]

# 공식 분류 HE_DM_HbA1c의 당뇨병 코드
OFFICIAL_DIABETES_CODE = 3

# 설문 문항의 모름·무응답 코드
UNKNOWN_RESPONSE_CODE = 9

# 값이 없거나 모름이면 음성으로 확정할 수 없는 설문 문항
MODEL_REQUIRED_RESPONSE_VARS_MAP = {
    ModelType.DIABETES_RISK: ["DE1_dg", "DE1_31", "DE1_32"],
    ModelType.HYPERTENSION_RISK: ["DI1_pr", "DI1_2"],
}
