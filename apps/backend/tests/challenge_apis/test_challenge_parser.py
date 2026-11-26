import pytest

from app.core.enums import ChallengeType
from app.services.challenge_parser import ChallengeParseError, parse_challenge_response, parse_challenges
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


# ---------- 근거 없는 일반 습관 챌린지 허용 수 ----------


def test_parse_allows_general_challenges_only_for_missing_count() -> None:
    # 근거 요인 2개, 추천 3개 → 일반 습관은 1개까지
    text = challenges_json(
        [
            challenge_item(),
            challenge_item(title="주 3회 근력 운동", challenge_type="WEEKLY", total_rounds=4, basis_features=[]),
            challenge_item(title="주 3회 싱겁게 먹기", challenge_type="WEEKLY", total_rounds=4, basis_features=[]),
        ]
    )

    result = parse_challenge_response(text, allowed_features=FEATURES, allowed_diseases=DISEASES, max_count=3)

    assert [challenge.title for challenge in result.challenges] == ["매일 30분 빠르게 걷기", "주 3회 근력 운동"]
    assert result.reasons == ["3번째 챌린지: 근거 요인이 있으므로 basis_features에 근거 요인을 적어야 합니다"]


def test_parse_rejects_general_challenge_when_factors_cover_count() -> None:
    features = {"허리둘레": {"diabetes_risk"}, "BMI": {"diabetes_risk"}, "중성지방": {"diabetes_risk"}}

    reasons = reasons_of(challenges_json([challenge_item(basis_features=[])]), features)

    assert reasons == ["1번째 챌린지: 근거 요인이 있으므로 basis_features에 근거 요인을 적어야 합니다"]


def test_parse_response_returns_reasons_with_valid_challenges() -> None:
    text = challenges_json([challenge_item(), challenge_item(title="BMI", basis_features=["나이"])])

    result = parse_challenge_response(text, allowed_features=FEATURES, allowed_diseases=DISEASES, max_count=3)

    assert len(result.challenges) == 1
    assert result.reasons == ["2번째 챌린지: 근거로 쓸 수 없는 요인입니다(나이)"]


# ---------- 제목 빈도와 유형 ----------


@pytest.mark.parametrize(
    ("title", "challenge_type", "total_rounds"),
    [
        ("주 3회 30분 걷기", "DAILY", 14),
        ("한 달에 4번 등산하기", "DAILY", 14),
        ("매일 30분 걷기", "WEEKLY", 4),
        ("매일 물 8잔 마시기", "COUNT_BASED", 14),
        ("매일 채소 먹기", "MONTHLY", 2),
    ],
)
def test_parse_rejects_title_frequency_conflicting_with_type(
    title: str, challenge_type: str, total_rounds: int
) -> None:
    item = challenge_item(title=title, challenge_type=challenge_type, total_rounds=total_rounds)

    reasons = reasons_of(challenges_json([item]))

    assert "제목" in reasons[0]


@pytest.mark.parametrize(
    ("title", "challenge_type", "total_rounds"),
    [
        ("매일 식후 10분 걷기", "DAILY", 14),
        ("주 3회 근력 운동하기", "WEEKLY", 4),
        ("주 2일 술 없는 날 만들기", "WEEKLY", 4),
        ("한 달에 4번 등산하기", "MONTHLY", 2),
        ("술 없는 저녁 10번 만들기", "COUNT_BASED", 10),
    ],
)
def test_parse_accepts_title_frequency_matching_type(title: str, challenge_type: str, total_rounds: int) -> None:
    item = challenge_item(title=title, challenge_type=challenge_type, total_rounds=total_rounds)

    assert parse(challenges_json([item]))[0].title == title


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
