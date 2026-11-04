# knhanes 국민건강조사 변수 활용 매핑 상수
from src.enums import ModelType

KNHANES_VARIABLES_CONFIG_MAP = [
    {
        "name": "sex",
        "label": "성별",
        "type": "N(1)",
        "value_labels": ["1. 남자", "2. 여자"],
    },
    {
        "name": "age",
        "label": "나이",
        "type": "N(3)",
        "value_labels": ["1~79. 1~79세", "80. 80세이상"],
    },
    {
        "name": "DI1_pr",
        "label": "고혈압 유병 여부",
        "type": "N(1)",
        "value_labels": ["0. 없음", "1. 있음", "8. 비해당 (소아, 청소년, 의사진단 받지 않음)", "9. 모름, 무응답"],
    },
    {
        "name": "DE1_pr",
        "label": "당뇨병 유병 여부",
        "type": "N(1)",
        "value_labels": ["0. 없음", "1. 있음", "8. 비해당 (소아, 청소년, 의사진단 받지 않음)", "9. 모름, 무응답"],
    },
    {
        "name": "BD1",
        "label": "평생음주경험",
        "type": "N(1)",
        "value_labels": ["1. 술을 마셔 본 적 없음", "2. 있음", "8. 비해당(소아)", "9. 모름, 무응답"],
    },
    {
        "name": "BD1_11",
        "label": "1년간 음주빈도",
        "type": "N(1)",
        "value_labels": [
            "1. 최근 1년간 전혀 마시지 않았다",
            "2. 월1회미만",
            "3. 월1회정도",
            "4. 월2-4회",
            "5. 주2-3회정도",
            "6. 주4회이상",
            "8. 비해당(문항1-⑧)",
            "9. 모름, 무응답",
        ],
    },
    {
        "name": "BD2_1",
        "label": "한 번에 마시는 음주량",
        "type": "N(1)",
        "value_labels": [
            "1. 1-2잔",
            "2. 3-4잔",
            "3. 5-6잔",
            "4. 7-9잔",
            "5. 10잔 이상",
            "8. 비해당(문항2-1-①⑧)",
            "9. 모름, 무응답",
        ],
    },
    {
        "name": "BS3_1",
        "label": "현재 흡연 여부",
        "type": "N(1)",
        "value_labels": [
            "1. 매일피움",
            "2. 가끔피움",
            "3. 과거엔 피웠으나, 현재 피우지 않음",
            "8. 비해당(문항1-③⑧)",
            "9. 모름, 무응답",
        ],
    },
    {
        "name": "BS3_2",
        "label": "하루평균 담배 흡연량",
        "type": "N(3)",
        "value_labels": ["□□□개비", "888. 비해당(문항3-③⑧)", "999. 모름, 무응답"],
    },
    {
        "name": "HE_HPfh1",
        "label": "고혈압 가족력(부)",
        "type": "N(1)",
        "value_labels": ["0. 아니오", "1. 예", "9. 모름/무응답"],
    },
    {
        "name": "HE_HPfh2",
        "label": "고혈압 가족력(모)",
        "type": "N(1)",
        "value_labels": ["0. 아니오", "1. 예", "9. 모름/무응답"],
    },
    {
        "name": "HE_HPfh3",
        "label": "고혈압 가족력(형제자매)",
        "type": "N(1)",
        "value_labels": ["0. 아니오", "1. 예", "8. 비해당", "9. 모름/무응답"],
    },
    {
        "name": "HE_DMfh1",
        "label": "당뇨병 가족력(부)",
        "type": "N(1)",
        "value_labels": ["0. 아니오", "1. 예", "9. 모름/무응답"],
    },
    {
        "name": "HE_DMfh2",
        "label": "당뇨병 가족력(모)",
        "type": "N(1)",
        "value_labels": ["0. 아니오", "1. 예", "9. 모름/무응답"],
    },
    {
        "name": "HE_DMfh3",
        "label": "당뇨병 가족력(형제자매)",
        "type": "N(1)",
        "value_labels": [
            "0. 아니오",
            "1. 예",
            "8. 비해당",
            "9. 모름/무응답",
            "* 검진기본조사 자료는 HNYR_ALL (YR은 해당연도 두자리수) DB에 포함",
            "■ 가족력",
        ],
    },
    {
        "name": "HE_sbp",
        "label": "수축기 혈압",
        "type": "N(8)*",
        "value_labels": ["□□□ mmHg"],
    },
    {
        "name": "HE_dbp",
        "label": "이완기 혈압",
        "type": "N(8)*",
        "value_labels": ["□□□ mmHg"],
    },
    {
        "name": "HE_ht",
        "label": "키",
        "type": "N(8.1)",
        "value_labels": ["□□□.□ cm"],
    },
    {
        "name": "HE_wt",
        "label": "체중",
        "type": "N(8.1)",
        "value_labels": ["□□□.□ kg"],
    },
    {
        "name": "HE_wc",
        "label": "허리둘레",
        "type": "N(8.1)",
        "value_labels": ["□□□.□ cm"],
    },
    {
        "name": "HE_BMI",
        "label": "BMI",
        "type": "N(8.1)*",
        "value_labels": ["□□□.□ kg/m2"],
    },
    {
        "name": "HE_glu",
        "label": "공복혈당",
        "type": "N(8)",
        "value_labels": ["□□□ mg/dL"],
    },
    {
        "name": "HE_HbA1c",
        "label": "당화혈색소",
        "type": "N(8.1)",
        "value_labels": ["□□.□ %"],
    },
    {
        "name": "HE_chol",
        "label": "총콜레스테롤",
        "type": "N(8)",
        "value_labels": ["□□□ mg/dL"],
    },
    {
        "name": "HE_HDL_st2",
        "label": "HDL-콜레스테롤",
        "type": "N(8)",
        "value_labels": ["□□□ mg/dL"],
    },
    {
        "name": "HE_TG",
        "label": "중성지방",
        "type": "N(8)",
        "value_labels": ["□□□□ mg/dL"],
    },
    {
        "name": "HE_ast",
        "label": "AST",
        "type": "N(8)",
        "value_labels": ["□□□ IU/L"],
    },
    {
        "name": "HE_alt",
        "label": "ALT",
        "type": "N(8)",
        "value_labels": ["□□□ IU/L"],
    },
    {
        "name": "HE_crea",
        "label": "혈중크레아티닌",
        "type": "N(8.2)",
        "value_labels": ["□.□□ mg/dL", "■ 일반혈액 검사"],
    },
    {
        "name": "HE_Upro",
        "label": "요단백",
        "type": "N(1)",
        "value_labels": ["0. 음성(-) 1. 미량(±) 2. 양성(+) 3. 양성(++) 4. 양성(+++) 5. 양성(++++)"],
    },
    {
        "name": "HE_Uglu",
        "label": "요당",
        "type": "N(1)",
        "value_labels": ["0. 음성(-) 1. 미량(±) 2. 양성(+) 3. 양성(++) 4. 양성(+++) 5. 양성(++++)"],
    },
]

MODEL_VARIABLES_MAP = {
    "common": [
        # 인구학적
        "sex",
        "age",
        # 비만/체형
        "HE_ht",
        "HE_wt",
        "HE_wc",
        "HE_BMI",
        # 생활습관 (음주/흡연)
        "BD1",
        "BD1_11",
        "BD2_1",
        "BS3_1",
        "BS3_2",
        # 혈액 검사 수치 (간/전신)
        "HE_chol",
        "HE_HDL_st2",
        "HE_TG",
        "HE_ast",
        "HE_alt",
        "HE_crea",
        # 신장 및 심혈관 수치
        "HE_Upro",
    ],
    ModelType.DIABETES_RISK: [
        "DE1_pr",  # 타겟 변수
        "HE_sbp",
        "HE_dbp",  # 수축기/이완기 혈압
        "DI1_pr",  # 고혈압 유병 여부
        "HE_DMfh1",
        "HE_DMfh2",
        "HE_DMfh3",  # 당뇨 가족력
    ],
    ModelType.HYPERTENSION_RISK: [
        "DI1_pr",  # 타겟 변수
        "HE_glu",
        "HE_HbA1c",  # 공복혈당, 당화혈색소 (고혈압 예측의 강력한 피처)
        "DE1_pr",  # 당뇨 유병 여부
        "HE_Uglu",  # 요당
        "HE_HPfh1",
        "HE_HPfh2",
        "HE_HPfh3",  # 고혈압 가족력
    ],
}

MODEL_TARGET_VAR_MAP = {
    ModelType.DIABETES_RISK: "DE1_pr",
    ModelType.HYPERTENSION_RISK: "DI1_pr",
}

# 변수 역할 분리 기준: 제8·9기 원시자료 이용지침서와 2020~2024 원시자료 대조 결과
# MODEL_VARIABLES_MAP의 타겟 변수는 라벨 생성 단계가 구현될 때까지 전처리기 호환을 위해 유지한다.

# 식별·분할 변수: ID_fam은 가구 단위 분할, year는 연도 단위 분할에 사용
IDENTIFIER_VARS = ["ID", "ID_fam", "year"]

# 표본 설계 변수: 가중치, 층, 집락
SURVEY_DESIGN_VARS = ["wt_itvex", "wt_tot", "kstrata", "psu"]

# 학습 제외 변수: HE_prg = 1 또는 HE_dprg(임신개월수) 값이 있으면 임신 중 응답자
PREGNANCY_EXCLUSION_VARS = ["HE_prg", "HE_dprg"]

# 입력 피처 제외 변수: HE_fh는 2023~2024년 하위 항목과 불일치, HE_insulin은 2022년부터 미제공
UNUSABLE_INPUT_VARS = ["HE_fh", "HE_insulin"]

# 라벨 생성에 사용하는 원천 변수
MODEL_LABEL_SOURCE_VARS_MAP = {
    ModelType.DIABETES_RISK: [
        "DE1_dg",  # 의사 진단 (1 = 있음)
        "DE1_31",  # 인슐린 (1 = 예)
        "DE1_32",  # 당뇨병약 (1 = 예)
        "HE_glu",  # 공복혈당 (126 mg/dL 이상)
        "HE_fst",  # 공복 시간 (8시간 이상일 때만 공복혈당 사용)
        "HE_HbA1c",  # 당화혈색소 (6.5% 이상)
    ],
    ModelType.HYPERTENSION_RISK: [
        "DI1_pr",  # 현재 유병 (1 = 있음)
        "DI1_2",  # 혈압조절제 복용 (1~4 = 복용, 5 = 미복용)
        "HE_sbp",  # 수축기 혈압 (140 mmHg 이상)
        "HE_dbp",  # 이완기 혈압 (90 mmHg 이상)
    ],
}

# 공식 분류 변수: 생성한 라벨의 대조에만 사용
# HE_DM_HbA1c = 3이 당뇨병, HE_HP는 2020~2021년 3, 2022년부터 4가 고혈압
MODEL_OFFICIAL_LABEL_VAR_MAP = {
    ModelType.DIABETES_RISK: "HE_DM_HbA1c",
    ModelType.HYPERTENSION_RISK: "HE_HP",
}

# 라벨 원천은 아니지만 해당 질환의 진단 정보를 담고 있는 변수
MODEL_DIAGNOSIS_PROXY_VARS_MAP = {
    ModelType.DIABETES_RISK: ["DE1_pr"],
    ModelType.HYPERTENSION_RISK: ["DI1_dg"],
}

# 모델별 입력 피처: 공통 입력과 모델별 입력에서 타겟 변수를 제외한 목록
MODEL_INPUT_VARS_MAP = {
    model_type: [
        var_name
        for var_name in MODEL_VARIABLES_MAP["common"] + MODEL_VARIABLES_MAP[model_type]
        if var_name != target_var
    ]
    for model_type, target_var in MODEL_TARGET_VAR_MAP.items()
}

# 모델별 입력 금지 변수
MODEL_FORBIDDEN_INPUT_VARS_MAP = {
    model_type: [
        *IDENTIFIER_VARS,
        *SURVEY_DESIGN_VARS,
        *PREGNANCY_EXCLUSION_VARS,
        *UNUSABLE_INPUT_VARS,
        *MODEL_OFFICIAL_LABEL_VAR_MAP.values(),
        *MODEL_LABEL_SOURCE_VARS_MAP[model_type],
        *MODEL_DIAGNOSIS_PROXY_VARS_MAP[model_type],
    ]
    for model_type in MODEL_TARGET_VAR_MAP
}
