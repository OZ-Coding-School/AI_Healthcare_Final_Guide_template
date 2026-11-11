# KNHANES 위험도 추론 설정
from core.config import settings
from src.enums import ModelType

# 서빙 아티팩트 위치: 모델마다 폴더 1개, 버전은 metadata.json과 매니페스트에 기록
#
# artifacts/models/knhanes_serving/
# ├── serving_manifest.json        모델별 폴더와 metadata.json 해시
# └── diabetes_risk_model/
#     ├── model.pkl                학습된 분류기
#     ├── preprocessor.pkl         Train에만 fit한 전처리기 (결측 대치, 원-핫 등)
#     ├── calibrator.pkl           확률 보정기
#     ├── thresholds.json          위험 등급 경계와 산출 기준
#     └── metadata.json            출처, 입력 스키마, 학습 범위, 버전, 파일 해시
SERVING_MODEL_DIR = settings.MODEL_DIR / "knhanes_serving"
SERVING_MANIFEST_NAME = "serving_manifest.json"
SERVING_BUNDLE_SCHEMA_VERSION = 2

SERVING_MODEL_FILE = "model.pkl"
SERVING_PREPROCESSOR_FILE = "preprocessor.pkl"
SERVING_CALIBRATOR_FILE = "calibrator.pkl"
SERVING_THRESHOLDS_FILE = "thresholds.json"
SERVING_METADATA_FILE = "metadata.json"
SERVING_HASHED_FILES = [
    SERVING_MODEL_FILE,
    SERVING_PREPROCESSOR_FILE,
    SERVING_CALIBRATOR_FILE,
    SERVING_THRESHOLDS_FILE,
]


def serving_model_dirname(model_type: ModelType) -> str:
    return f"{model_type}_model"


# metadata.json의 필수 항목: 없으면 학습 결과와 연결할 수 없어 로드를 거부
SERVING_METADATA_REQUIRED_KEYS = [
    "schema_version",
    "model_type",
    "train_set",
    "algorithm",
    "hyperparameters",
    "calibration_method",
    "source_model_sha256",
    "training_data_sha256",
    "created_at",
    "library_versions",
    "input_schema",
    "numeric_ranges",
    "feature_names",
    "feature_metadata",
    "files",
]

# 버전이 다르면 경고하는 라이브러리(배포 이름): 번들의 직렬화·예측에 직접 관여
SERVING_TRACKED_LIBRARIES = ["scikit-learn", "lightgbm", "xgboost", "shap", "numpy", "pandas", "joblib"]

# KNHANES는 80세 이상을 80으로 기록하므로 추론 입력도 같은 상한을 적용
KNHANES_AGE_TOP_CODE = 80

# 서비스 입력의 허용 범위: 측정·입력 오류로 볼 수 있는 값은 거부 (단위는 Backend 스키마 기준)
SERVICE_INPUT_RANGES: dict[str, tuple[float, float]] = {
    "height": (100.0, 230.0),  # cm
    "weight": (25.0, 250.0),  # kg
    "waist_circumference": (40.0, 200.0),  # cm
    "sbp": (60, 260),  # mmHg
    "dbp": (30, 160),  # mmHg
    "fbs": (40, 600),  # mg/dL
    "hba1c": (3.0, 20.0),  # %
    "triglyceride": (10, 3000),  # mg/dL
    "total_cholesterol": (50, 600),  # mg/dL
    "hdl": (5, 200),  # mg/dL
    "ast": (1, 2000),  # IU/L
    "alt": (1, 2000),  # IU/L
    "creatinine": (0.1, 20.0),  # mg/dL
    "cigarettes_per_day": (0, 100),  # 개비
    "drinks_per_session": (0, 50),  # 잔 (소주잔 기준)
}

# 회당 음주 잔 수 → KNHANES BD2_1 코드 (1: 1~2잔, 2: 3~4잔, 3: 5~6잔, 4: 7~9잔, 5: 10잔 이상)
DRINKS_PER_SESSION_CODE_BINS: list[tuple[int, int]] = [
    (2, 1),
    (4, 2),
    (6, 3),
    (9, 4),
]
DRINKS_PER_SESSION_MAX_CODE = 5

# 사용자 화면·LLM에 보일 표시명 (키: 전처리 후 컬럼명)
FEATURE_DISPLAY_NAME_MAP = {
    "성별": "성별",
    "나이": "나이",
    "키": "키",
    "체중": "체중",
    "허리둘레": "허리둘레",
    "BMI": "체질량지수(BMI)",
    "평생음주경험": "음주 경험",
    "1년간 음주빈도": "음주 빈도",
    "한 번에 마시는 음주량": "1회 음주량",
    "현재 흡연 여부": "흡연 상태",
    "하루평균 담배 흡연량": "하루 흡연량",
    "총콜레스테롤": "총콜레스테롤",
    "HDL-콜레스테롤": "HDL 콜레스테롤",
    "중성지방": "중성지방",
    "AST": "간 수치(AST)",
    "ALT": "간 수치(ALT)",
    "혈중크레아티닌": "혈중 크레아티닌",
    "요단백": "요단백",
    "요당": "요당",
    "수축기 혈압": "수축기 혈압",
    "이완기 혈압": "이완기 혈압",
    "공복혈당": "공복혈당",
    "당화혈색소": "당화혈색소(HbA1c)",
    "고혈압 유병 여부": "고혈압 진단 여부",
    "당뇨병 유병 여부": "당뇨병 진단 여부",
    "당뇨병 가족력(부)": "당뇨병 가족력(아버지)",
    "당뇨병 가족력(모)": "당뇨병 가족력(어머니)",
    "당뇨병 가족력(형제자매)": "당뇨병 가족력(형제자매)",
    "당뇨병 가족력 보유 여부": "당뇨병 가족력",
    "고혈압 가족력(부)": "고혈압 가족력(아버지)",
    "고혈압 가족력(모)": "고혈압 가족력(어머니)",
    "고혈압 가족력(형제자매)": "고혈압 가족력(형제자매)",
    "고혈압 가족력 보유 여부": "고혈압 가족력",
}

# 생활습관으로 바꿀 수 없는 요인: 챌린지 추천(14번)의 근거로 쓰지 않음
NON_ACTIONABLE_FEATURES = {
    "성별",
    "나이",
    "키",
    "고혈압 유병 여부",
    "당뇨병 유병 여부",
    "당뇨병 가족력(부)",
    "당뇨병 가족력(모)",
    "당뇨병 가족력(형제자매)",
    "당뇨병 가족력 보유 여부",
    "고혈압 가족력(부)",
    "고혈압 가족력(모)",
    "고혈압 가족력(형제자매)",
    "고혈압 가족력 보유 여부",
}

# 역인과가 의심되는 요인: 치료 중인 환자의 약물 영향 등으로 방향이 뒤집혔을 수 있음
# 총콜레스테롤은 두 모델 모두 값이 높을수록 위험도를 낮춤 (Validation SHAP 스피어만: 당뇨 -0.95, 고혈압 -0.97)
# 응답에는 포함하되 챌린지 추천 근거로 쓰지 않음
REVERSE_CAUSATION_SUSPECTED_FEATURES_MAP: dict[ModelType, set[str]] = {
    ModelType.DIABETES_RISK: {"총콜레스테롤"},
    ModelType.HYPERTENSION_RISK: {"총콜레스테롤"},
}

# 로컬 설명에서 반환할 상위 요인 수 (원 변수 단위)
SHAP_TOP_K = 5
