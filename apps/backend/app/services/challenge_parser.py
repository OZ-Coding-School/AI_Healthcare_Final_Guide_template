"""
LLM 챌린지 추천 응답을 검증해 저장 가능한 챌린지 목록으로 바꿉니다. DB·네트워크에 의존하지 않는 순수 함수입니다.

검증 순서
    1. 코드펜스를 벗기고 JSON으로 읽습니다. {"challenges": [...]} 형태여야 합니다.
    2. 항목마다 필드·타입·챌린지 유형·길이(DB 컬럼 길이)·목표 회차 범위를 검증합니다.
    3. 제목의 빈도가 챌린지 유형과 어긋나는 항목(예: WEEKLY인데 "매일")을 뺍니다.
    4. 근거 요인(basis_features)과 질환(target_diseases)이 프롬프트로 준 목록 안에 있고,
       근거 요인이 target_diseases 중 하나의 위험을 높인 요인인지 확인합니다.
    5. 의료 행위로 오해될 표현(약 복용·처방·치료 등)이 있는 항목을 뺍니다.
    6. 제목이 겹치는 항목을 뺍니다.
    7. 근거 없는 일반 습관 챌린지는 근거 요인이 개수보다 적어 모자란 만큼만 남깁니다.
       (근거 요인이 있는데도 일반 습관으로 채우는 것을 막습니다.)
    8. 최대 개수까지만 남깁니다.
문제가 있는 항목만 버리고, 남은 항목이 하나도 없으면 ChallengeParseError를 냅니다.
버린 이유는 ChallengeParseResult.reasons로 돌려주어, 개수가 모자랄 때 재요청 메시지와 로그에 씁니다.
"""

import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.enums import ChallengeType
from app.services.challenge_prompt import (
    DESCRIPTION_MAX_LENGTH,
    EXPECTED_EFFECT_MAX_LENGTH,
    ROUND_RANGES,
    TITLE_MAX_LENGTH,
)

_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)

# 의료 행위(진단·약물·처방·치료)로 오해될 수 있는 표현입니다. 예방 차원의 "의료진 상담" 권유는 허용합니다.
_MEDICAL_EXPRESSIONS = re.compile(
    r"약물|복용|투약|처방|인슐린|혈압약|당뇨약|혈당강하제|완치|치료법|치료하|진단하|진단을 받|약을\s*(끊|줄|늘|중단)"
)


# 제목의 빈도 표현. 챌린지 유형과 어긋나면 사용자가 무엇을 얼마나 해야 하는지 헷갈리므로 버립니다.
_EVERY_DAY = re.compile(r"매일")
_PER_WEEK_OR_MONTH = re.compile(r"(주|매주|일주일에?|월|매달|한\s*달에?)\s*\d+\s*(회|일|번)")


def _frequency_conflict(challenge_type: ChallengeType, title: str) -> str | None:
    """제목의 빈도가 유형과 어긋나면 이유를, 맞으면 None을 반환합니다."""
    if challenge_type is ChallengeType.DAILY:
        match = _PER_WEEK_OR_MONTH.search(title)
        if match:
            return f"DAILY는 매일 하는 챌린지인데 제목에 '{match.group(0)}'가 있습니다. WEEKLY 또는 MONTHLY로 바꾸세요"
    elif _EVERY_DAY.search(title):
        return f"{challenge_type}인데 제목에 '매일'이 있습니다. 매일 하는 행동이면 DAILY로 바꾸세요"
    return None


class ChallengeParseError(ValueError):
    """사용할 수 있는 챌린지가 하나도 없습니다. reasons는 재요청 메시지에 씁니다."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons) or "No valid challenge in LLM response.")
        self.reasons = reasons


@dataclass(frozen=True)
class ParsedChallenge:
    title: str
    description: str
    challenge_type: ChallengeType
    total_rounds: int
    expected_effect: str
    target_diseases: list[str]
    basis_features: list[str]


class _ChallengeItem(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    challenge_type: ChallengeType
    total_rounds: int
    expected_effect: str = Field(min_length=1, max_length=EXPECTED_EFFECT_MAX_LENGTH)
    target_diseases: list[str] = Field(min_length=1)
    basis_features: list[str] = Field(default_factory=list)

    @field_validator("target_diseases", "basis_features")
    @classmethod
    def unique(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


@dataclass(frozen=True)
class ChallengeParseResult:
    challenges: list[ParsedChallenge]
    reasons: list[str]  # 버린 항목의 이유. 모두 통과했으면 빈 목록입니다.


def parse_challenges(
    text: str,
    allowed_features: Mapping[str, Collection[str]],
    allowed_diseases: Collection[str],
    max_count: int,
) -> list[ParsedChallenge]:
    """검증을 통과한 챌린지만 반환합니다. 버린 이유가 필요하면 parse_challenge_response를 씁니다."""
    return parse_challenge_response(text, allowed_features, allowed_diseases, max_count).challenges


def parse_challenge_response(
    text: str,
    allowed_features: Mapping[str, Collection[str]],
    allowed_diseases: Collection[str],
    max_count: int,
) -> ChallengeParseResult:
    """
    :param allowed_features: 근거로 쓸 수 있는 feature → 그 요인이 위험을 높인 질환(model_type) 목록
    :param allowed_diseases: target_diseases로 쓸 수 있는 질환(model_type) 목록
    :param max_count: 추천할 챌린지 수. 근거 없는 일반 습관 챌린지 허용 수도 이 값으로 정합니다.
    """
    items = _load_items(text)
    reasons: list[str] = []
    parsed: list[ParsedChallenge] = []
    seen_titles: set[str] = set()
    # 근거 요인이 개수보다 적을 때 모자란 만큼만 일반 습관 챌린지를 허용합니다. 요인이 없으면 전부 일반 습관입니다.
    general_allowed = max(0, max_count - len(allowed_features))
    general_count = 0
    for index, raw in enumerate(items, start=1):
        try:
            challenge = _validate_item(raw, allowed_features, allowed_diseases)
        except ValueError as error:
            reasons.append(f"{index}번째 챌린지: {error}")
            continue
        key = re.sub(r"\s+", "", challenge.title)
        if key in seen_titles:
            reasons.append(f"{index}번째 챌린지: 제목이 다른 챌린지와 겹칩니다")
            continue
        if not challenge.basis_features:
            if general_count >= general_allowed:
                reasons.append(f"{index}번째 챌린지: 근거 요인이 있으므로 basis_features에 근거 요인을 적어야 합니다")
                continue
            general_count += 1
        seen_titles.add(key)
        parsed.append(challenge)

    if not parsed:
        raise ChallengeParseError(reasons or ["challenges 배열이 비어 있습니다"])
    return ChallengeParseResult(challenges=parsed[:max_count], reasons=reasons)


def _load_items(text: str) -> list[Any]:
    match = _CODE_FENCE.match(text)
    body = match.group(1) if match else text.strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise ChallengeParseError(["응답이 JSON 형식이 아닙니다"]) from None
    if not isinstance(data, dict) or not isinstance(data.get("challenges"), list):
        raise ChallengeParseError(['응답은 {"challenges": [...]} 형식이어야 합니다'])
    return data["challenges"]


def _validate_item(
    raw: Any, allowed_features: Mapping[str, Collection[str]], allowed_diseases: Collection[str]
) -> ParsedChallenge:
    if not isinstance(raw, dict):
        raise ValueError("객체 형식이 아닙니다")
    try:
        item = _ChallengeItem.model_validate(raw)
    except ValidationError as error:
        fields = sorted({".".join(str(loc) for loc in detail["loc"]) for detail in error.errors()})
        raise ValueError(f"필드 형식 또는 길이가 맞지 않습니다({', '.join(fields)})") from None

    low, high = ROUND_RANGES[item.challenge_type]
    if not low <= item.total_rounds <= high:
        raise ValueError(f"{item.challenge_type}의 total_rounds는 {low}~{high}이어야 합니다")
    conflict = _frequency_conflict(item.challenge_type, item.title)
    if conflict:
        raise ValueError(conflict)
    unknown_diseases = [disease for disease in item.target_diseases if disease not in allowed_diseases]
    if unknown_diseases:
        raise ValueError(f"알 수 없는 질환입니다({', '.join(unknown_diseases)})")
    unknown_features = [feature for feature in item.basis_features if feature not in allowed_features]
    if unknown_features:
        raise ValueError(f"근거로 쓸 수 없는 요인입니다({', '.join(unknown_features)})")
    unrelated = [
        feature for feature in item.basis_features if not set(allowed_features[feature]) & set(item.target_diseases)
    ]
    if unrelated:
        raise ValueError(f"근거 요인이 target_diseases의 질환에 속하지 않습니다({', '.join(unrelated)})")
    text = " ".join((item.title, item.description, item.expected_effect))
    if _MEDICAL_EXPRESSIONS.search(text):
        raise ValueError("약물·처방·치료처럼 의료 행위로 오해될 표현이 있습니다")

    return ParsedChallenge(
        title=item.title,
        description=item.description,
        challenge_type=item.challenge_type,
        total_rounds=item.total_rounds,
        expected_effect=item.expected_effect,
        target_diseases=item.target_diseases,
        basis_features=item.basis_features,
    )
