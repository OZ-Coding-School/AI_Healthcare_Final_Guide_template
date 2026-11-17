import pytest

from app.core.enums import ChallengeType, DiseaseRiskLevel, HabitStatus, PredictionModelType
from app.services.challenge_prompt import build_challenge_prompt, build_retry_message, select_basis_factors
from tests.challenge_apis.helpers import factor, result, survey

DIABETES = PredictionModelType.DIABETES_RISK
HYPERTENSION = PredictionModelType.HYPERTENSION_RISK


def test_select_basis_factors_excludes_non_actionable_reverse_decrease_and_out_of_range() -> None:
    results = [
        result(
            DIABETES,
            [
                factor("나이", 0.9, actionable=False),
                factor("총콜레스테롤", 0.5, reverse=True),
                factor("HDL-콜레스테롤", -0.3),
                factor("중성지방", 0.2),
                factor("허리둘레", 0.4),
                factor("ALT", 0.6),
            ],
            out_of_training_range=["ALT"],
        )
    ]

    factors = select_basis_factors(results)

    assert [(item.feature, item.rank) for item in factors] == [("허리둘레", 1), ("중성지방", 2)]


def test_select_basis_factors_keeps_disease_order_and_rank_per_disease() -> None:
    results = [
        result(HYPERTENSION, [factor("BMI", 0.3)]),
        result(DIABETES, [factor("허리둘레", 0.1), factor("중성지방", 0.2)]),
    ]

    factors = select_basis_factors(results)

    assert [(item.model_type, item.feature, item.rank) for item in factors] == [
        (DIABETES, "중성지방", 1),
        (DIABETES, "허리둘레", 2),
        (HYPERTENSION, "BMI", 1),
    ]


def test_build_prompt_contains_risk_factors_and_habits_without_shap_numbers() -> None:
    results = [
        result(DIABETES, [factor("허리둘레", 0.0812, value=92.0), factor("나이", 0.05, actionable=False)]),
        result(HYPERTENSION, [factor("BMI", 0.12, display_name="체질량지수(BMI)", value=26.2)]),
    ]

    prompt = build_challenge_prompt(results, survey(), count=3)

    assert "챌린지 3개" in prompt.user
    assert "당뇨병(diabetes_risk): 위험 등급 중간(MODERATE), 위험도 23%" in prompt.user
    assert "feature: 허리둘레 | 표시명: 허리둘레 | 현재 값: 92 | 질환: diabetes_risk | 순위: 1" in prompt.user
    assert "표시명: 체질량지수(BMI)" in prompt.user
    assert "흡연: 하고 있음 (하루 10개비)" in prompt.user
    assert "음주: 하고 있음 (주 2~3회, 1회 5잔)" in prompt.user
    assert "나이" not in prompt.user.split("[근거로 쓸 수 있는 요인]")[1]
    assert "0.0812" not in prompt.user
    assert prompt.allowed_features == {"허리둘레": {"diabetes_risk"}, "BMI": {"hypertension_risk"}}
    assert prompt.target_diseases == (DIABETES, HYPERTENSION)


def test_build_prompt_asks_medical_consultation_only_for_high_risk() -> None:
    moderate = build_challenge_prompt([result(DIABETES, [factor("허리둘레", 0.1)])], survey(), count=3)
    high = build_challenge_prompt(
        [result(DIABETES, [factor("허리둘레", 0.1)], risk_level=DiseaseRiskLevel.HIGH)], survey(), count=3
    )

    assert "의료진 상담" not in moderate.user
    assert "의료진 상담을 권하는 문장" in high.user


def test_build_prompt_for_non_smoker_and_missing_survey() -> None:
    non_smoker = build_challenge_prompt(
        [result(DIABETES, [])],
        survey(smoking_status=HabitStatus.NEVER, smoking_fr_per_day=None, drinking_status=HabitStatus.NEVER),
        count=3,
    )
    no_survey = build_challenge_prompt([result(DIABETES, [])], None, count=3)

    assert "흡연: 전혀 없음" in non_smoker.user
    assert "(없음: 생활습관으로 바꿀 수 있는 위험 요인이 확인되지 않았습니다)" in non_smoker.user
    assert "월간 설문 정보 없음" in no_survey.user


def test_output_schema_restricts_features_and_diseases_with_enum() -> None:
    prompt = build_challenge_prompt([result(DIABETES, [factor("허리둘레", 0.1)])], survey(), count=3)
    item = prompt.schema["properties"]["challenges"]["items"]

    assert prompt.schema["additionalProperties"] is False
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert item["properties"]["basis_features"]["items"]["enum"] == ["허리둘레"]
    assert item["properties"]["target_diseases"]["items"]["enum"] == ["diabetes_risk"]
    assert item["properties"]["challenge_type"]["enum"] == [str(value) for value in ChallengeType]


def test_output_schema_without_basis_factors_has_no_empty_enum() -> None:
    prompt = build_challenge_prompt([result(DIABETES, [])], survey(), count=3)
    basis_items = prompt.schema["properties"]["challenges"]["items"]["properties"]["basis_features"]["items"]

    assert basis_items == {"type": "string"}


def test_basis_for_keeps_only_target_disease_factors() -> None:
    prompt = build_challenge_prompt(
        [
            result(DIABETES, [factor("BMI", 0.1, display_name="체질량지수(BMI)")]),
            result(HYPERTENSION, [factor("BMI", 0.2, display_name="체질량지수(BMI)")]),
        ],
        survey(),
        count=3,
    )

    assert prompt.allowed_features == {"BMI": {"diabetes_risk", "hypertension_risk"}}
    assert prompt.basis_for(["BMI"], ["diabetes_risk"]) == [
        {"model_type": "diabetes_risk", "feature": "BMI", "display_name": "체질량지수(BMI)"}
    ]
    assert len(prompt.basis_for(["BMI"], ["diabetes_risk", "hypertension_risk"])) == 2


def test_build_retry_message_appends_reasons() -> None:
    prompt = build_challenge_prompt([result(DIABETES, [factor("허리둘레", 0.1)])], survey(), count=3)

    message = build_retry_message(prompt, ["1번째 챌린지: 제목이 너무 깁니다"])

    assert message.startswith(prompt.user)
    assert "[이전 응답의 문제]\n- 1번째 챌린지: 제목이 너무 깁니다" in message


def test_build_prompt_requires_results() -> None:
    with pytest.raises(ValueError):
        build_challenge_prompt([], survey(), count=3)
