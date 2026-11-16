import pytest

from app.core.enums import ChallengeType
from app.services.challenge_parser import ChallengeParseError, parse_challenges
from tests.challenge_apis.helpers import challenge_item, challenges_json

FEATURES: dict[str, set[str]] = {"허리둘레": {"diabetes_risk", "hypertension_risk"}, "BMI": {"diabetes_risk"}}
DISEASES = {"diabetes_risk", "hypertension_risk"}


def parse(text: str, features: dict[str, set[str]] = FEATURES, max_count: int = 3):
    return parse_challenges(text, allowed_features=features, allowed_diseases=DISEASES, max_count=max_count)


def reasons_of(text: str, features: dict[str, set[str]] = FEATURES) -> list[str]:
    with pytest.raises(ChallengeParseError) as error:
        parse(text, features)
    return error.value.reasons


def test_parse_valid_response() -> None:
    challenges = parse(challenges_json([challenge_item()]))

    assert len(challenges) == 1
    challenge = challenges[0]
    assert challenge.title == "매일 30분 빠르게 걷기"
    assert challenge.challenge_type is ChallengeType.DAILY
    assert challenge.total_rounds == 21
    assert challenge.target_diseases == ["diabetes_risk"]
    assert challenge.basis_features == ["허리둘레"]


def test_parse_strips_code_fence_and_whitespace() -> None:
    text = "```json\n" + challenges_json([challenge_item(title="  매일 30분 빠르게 걷기  ")]) + "\n```"

    assert parse(text)[0].title == "매일 30분 빠르게 걷기"


@pytest.mark.parametrize("text", ["챌린지를 추천합니다", '{"items": []}', "[]", '{"challenges": []}'])
def test_parse_rejects_invalid_shape(text: str) -> None:
    assert reasons_of(text)


def test_parse_drops_invalid_items_and_keeps_valid_ones() -> None:
    text = challenges_json(
        [
            challenge_item(title="가" * 31),
            challenge_item(title="주 2회 근력 운동", challenge_type="YEARLY"),
            challenge_item(title="매일 물 마시기", total_rounds=3),
            challenge_item(title="BMI 낮추기", basis_features=["나이"]),
            challenge_item(title="혈압 관리", target_diseases=["obesity_risk"]),
            challenge_item(title="근거 없는 챌린지", basis_features=[]),
            challenge_item(title="혈압약 꾸준히 먹기", description="처방받은 약을 빠짐없이 복용합니다."),
            challenge_item(),
        ]
    )

    challenges = parse(text)

    assert [challenge.title for challenge in challenges] == ["매일 30분 빠르게 걷기"]


def test_parse_reports_reasons_when_all_items_invalid() -> None:
    reasons = reasons_of(
        challenges_json([challenge_item(total_rounds=100), challenge_item(title="BMI", basis_features=["나이"])])
    )

    assert reasons == [
        "1번째 챌린지: DAILY의 total_rounds는 7~30이어야 합니다",
        "2번째 챌린지: 근거로 쓸 수 없는 요인입니다(나이)",
    ]


@pytest.mark.parametrize(
    "text",
    ["치료법을 따라 합니다.", "인슐린 주사 시간을 지킵니다.", "약을 줄여 봅니다.", "진단을 받으세요."],
)
def test_parse_rejects_medical_expressions(text: str) -> None:
    assert reasons_of(challenges_json([challenge_item(description=text)]))


def test_parse_allows_consultation_and_everyday_words() -> None:
    description = "약간 숨이 찰 정도로 걷고, 위험도가 높다면 의료진과 상담해 보세요."

    assert parse(challenges_json([challenge_item(description=description)]))


def test_parse_removes_duplicate_titles_and_limits_count() -> None:
    text = challenges_json(
        [
            challenge_item(),
            challenge_item(title="매일 30분  빠르게 걷기"),
            challenge_item(title="주 3회 근력 운동", challenge_type="WEEKLY", total_rounds=4),
            challenge_item(title="한 달 금주", challenge_type="MONTHLY", total_rounds=1),
        ]
    )

    titles = [challenge.title for challenge in parse(text, max_count=2)]

    assert titles == ["매일 30분 빠르게 걷기", "주 3회 근력 운동"]


def test_parse_allows_empty_basis_when_no_factor_is_allowed() -> None:
    challenges = parse(challenges_json([challenge_item(basis_features=[])]), features={})

    assert challenges[0].basis_features == []


def test_parse_rejects_basis_unrelated_to_target_diseases() -> None:
    reasons = reasons_of(
        challenges_json([challenge_item(target_diseases=["hypertension_risk"], basis_features=["BMI"])])
    )

    assert reasons == ["1번째 챌린지: 근거 요인이 target_diseases의 질환에 속하지 않습니다(BMI)"]


def test_parse_deduplicates_list_values() -> None:
    item = challenge_item(target_diseases=["diabetes_risk", "diabetes_risk"], basis_features=["BMI", "BMI"])

    challenge = parse(challenges_json([item]))[0]

    assert challenge.target_diseases == ["diabetes_risk"]
    assert challenge.basis_features == ["BMI"]
