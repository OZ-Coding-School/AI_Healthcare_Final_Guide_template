"""
질병 위험도 예측 결과로 LLM 챌린지 추천 프롬프트를 만듭니다. DB·네트워크에 의존하지 않는 순수 함수입니다.

근거 요인 선정 규칙 (11번 추론 파이프라인 결정과 같음)
    - actionable=False(성별·나이·키·가족력·진단 여부)는 생활습관으로 바꿀 수 없어 제외합니다.
    - reverse_causation_suspected=True(총콜레스테롤)는 치료 영향으로 방향이 뒤집혔을 수 있어 제외합니다.
    - out_of_training_range에 있는 변수는 SHAP 설명을 믿기 어려워 제외합니다.
    - 위험을 높이는(direction=increase) 요인만 사용합니다.
    - SHAP 값은 숫자 대신 질환 안에서의 순위로만 전달합니다 (log-odds 값을 LLM이 확률로 오해하지 않도록).

개인정보 보호를 위해 이름·이메일·생년월일 등 사용자 식별 정보는 프롬프트에 넣지 않습니다.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.core.enums import ChallengeType, DiseaseRiskLevel, DrinkingFrequency, HabitStatus, PredictionModelType
from app.models.disease_prediction_models import DiseasePredictionResult
from app.models.health_profiles import MonthlyHealthSurvey

INCREASE = "increase"

# 챌린지 유형별 목표 회차 범위 (단위: 일간=일, 주간=주, 월간=개월, 횟수형=횟수)
ROUND_RANGES: dict[ChallengeType, tuple[int, int]] = {
    ChallengeType.DAILY: (7, 30),
    ChallengeType.WEEKLY: (2, 12),
    ChallengeType.MONTHLY: (1, 3),
    ChallengeType.COUNT_BASED: (3, 30),
}

# DB 컬럼 길이와 같게 유지합니다 (PersonalChallenge).
TITLE_MAX_LENGTH = 30
DESCRIPTION_MAX_LENGTH = 1000
EXPECTED_EFFECT_MAX_LENGTH = 300


# 횟수형 챌린지를 채워야 하는 기간(일). 챌린지 수락·기록 기능의 횟수형 기한과 같게 유지합니다.
COUNT_BASED_DAYS = 30


def _round_rule(challenge_type: ChallengeType, meaning: str, unit: str, example: str) -> str:
    low, high = ROUND_RANGES[challenge_type]
    return f'  - {challenge_type}: {meaning} total_rounds는 {unit} {low}~{high}. 제목 예: "{example}"'


SYSTEM_PROMPT = "\n".join(
    [
        "당신은 만성질환 예방을 돕는 생활습관 코치입니다.",
        "사용자의 당뇨병·고혈압 위험도 분석 결과를 보고, 일상에서 실천할 수 있는 생활습관 챌린지를 추천합니다.",
        "",
        "반드시 지킬 규칙",
        "1. 추천 근거는 [근거로 쓸 수 있는 요인] 목록에 있는 요인만 사용합니다. "
        "나이·성별·키·가족력처럼 목록에 없는 요인은 근거로 쓰지 않습니다.",
        '2. basis_features에는 목록의 "feature" 값을 그대로 적습니다. 근거 요인으로 먼저 챌린지를 만듭니다. '
        "근거 요인을 모두 다뤄도 요청한 개수가 모자랄 때만, basis_features를 빈 배열로 둔 일반 건강 습관 챌린지로 채웁니다. "
        "목록이 비어 있으면 모든 챌린지를 일반 건강 습관으로 추천합니다.",
        "3. 요청한 개수만큼 정확히 추천합니다. 더 적거나 많게 추천하지 않습니다.",
        "4. target_diseases에는 챌린지가 겨냥하는 질환의 model_type 값을 적습니다. "
        "근거 요인이 속한 질환을 포함해야 합니다. 일반 건강 습관은 위험 등급이 높은 질환을 적습니다.",
        "5. 의료 행위로 오해될 내용은 쓰지 않습니다: 진단, 약 복용·중단·용량 변경, 처방, 치료, 완치를 언급하지 않습니다.",
        '6. "위험이 30% 줄어듭니다"처럼 효과를 숫자로 약속하지 않습니다. 기대 효과는 일반적인 건강 효과로 설명합니다.',
        "7. [현재 생활습관]을 참고해 해당하지 않는 습관을 권하지 않습니다. 예: 비흡연자에게 금연 챌린지를 추천하지 않습니다.",
        "8. 목표는 [현재 생활습관]에서 출발해 기간 안에 무리 없이 해낼 수 있는 수준으로 정합니다. "
        "한 번에 끊거나 0으로 줄이게 하지 말고 단계적으로 줄이게 합니다. "
        '예: 하루 15개비를 피우면 "하루 10개비 이하로 줄이기", 주 4회 이상 마시면 "주 2일 술 없는 날 만들기"',
        "9. 서로 다른 행동을 다루는 챌린지를 추천합니다. 위험 등급이 높은 질환과 순위가 높은 요인을 먼저 다룹니다.",
        "10. 모든 문장은 한국어 존댓말로 씁니다.",
        "",
        "필드 작성 규칙",
        f'- title: {TITLE_MAX_LENGTH}자 이내. 무엇을 얼마나 하는지 드러나게 씁니다. 예: "매일 30분 빠르게 걷기"',
        f"- description: {DESCRIPTION_MAX_LENGTH}자 이내. 실천 방법을 구체적으로 2~4문장으로 씁니다.",
        f"- expected_effect: {EXPECTED_EFFECT_MAX_LENGTH}자 이내. 1~2문장으로 씁니다.",
        "- 제목과 설명에 나오는 빈도·횟수·시간은 서로 같아야 합니다. "
        '예: 제목이 "주 3회 걷기"면 설명도 주 3회를 기준으로 씁니다.',
        "- challenge_type은 제목의 빈도와 맞아야 하고, total_rounds(목표 회차)는 유형별 범위를 지킵니다.",
        _round_rule(ChallengeType.DAILY, "매일 하는 행동입니다. 하루가 1회차입니다.", "일 수", "매일 식후 10분 걷기"),
        _round_rule(
            ChallengeType.WEEKLY,
            "주마다 정한 횟수를 채우는 행동입니다. 한 주가 1회차입니다.",
            "주 수",
            "주 3회 근력 운동하기",
        ),
        _round_rule(
            ChallengeType.MONTHLY,
            "달마다 정한 목표를 채우는 행동입니다. 한 달이 1회차입니다.",
            "개월 수",
            "한 달에 4번 등산하기",
        ),
        _round_rule(
            ChallengeType.COUNT_BASED,
            f"날짜를 정하지 않고 실천한 날을 세는 행동입니다. 하루 1회까지 셀 수 있고, "
            f"{COUNT_BASED_DAYS}일 안에 total_rounds회를 채워야 합니다.",
            "횟수",
            "술 없는 저녁 10번 만들기",
        ),
        "- 회차 대부분을 성공해야 챌린지가 완료되므로, 한 회차의 분량은 매번 실천할 수 있을 만큼으로 정합니다.",
        "",
        "응답은 지정된 JSON 형식만 출력합니다.",
    ]
)


@dataclass(frozen=True)
class BasisFactor:
    """챌린지 근거로 쓸 수 있는 요인 1건입니다."""

    model_type: PredictionModelType
    feature: str
    display_name: str
    value: Any
    rank: int  # 질환 안에서의 기여 순위 (1이 가장 큼)


@dataclass(frozen=True)
class ChallengePrompt:
    system: str
    user: str
    schema: dict[str, Any]
    basis_factors: tuple[BasisFactor, ...]
    target_diseases: tuple[PredictionModelType, ...]
    count: int

    @property
    def allowed_features(self) -> dict[str, set[str]]:
        """근거로 쓸 수 있는 feature와, 그 요인이 위험을 높인 질환(model_type) 목록입니다."""
        allowed: dict[str, set[str]] = {}
        for factor in self.basis_factors:
            allowed.setdefault(factor.feature, set()).add(str(factor.model_type))
        return allowed

    def basis_for(self, features: Sequence[str], target_diseases: Sequence[str]) -> list[dict[str, str]]:
        """
        LLM이 고른 feature를 DB에 저장할 근거 목록({model_type, feature, display_name})으로 바꿉니다.
        같은 요인이 두 질환에 모두 있으면 챌린지가 겨냥하는 질환의 것만 남깁니다.
        """
        targets = set(target_diseases)
        return [
            {"model_type": str(factor.model_type), "feature": factor.feature, "display_name": factor.display_name}
            for feature in features
            for factor in self.basis_factors
            if factor.feature == feature and str(factor.model_type) in targets
        ]


def select_basis_factors(results: Sequence[DiseasePredictionResult]) -> list[BasisFactor]:
    """질환별 결과에서 챌린지 근거로 쓸 수 있는 요인만 순위대로 고릅니다."""
    factors: list[BasisFactor] = []
    for result in _sorted(results):
        excluded = set(result.out_of_training_range or [])
        candidates = [
            factor
            for factor in result.shap_results
            if factor.get("actionable")
            and not factor.get("reverse_causation_suspected")
            and factor.get("direction") == INCREASE
            and factor.get("feature") not in excluded
        ]
        candidates.sort(key=lambda factor: abs(float(factor.get("shap_value", 0.0))), reverse=True)
        factors.extend(
            BasisFactor(
                model_type=result.model_type,
                feature=str(factor["feature"]),
                display_name=str(factor.get("display_name") or factor["feature"]),
                value=factor.get("value"),
                rank=rank,
            )
            for rank, factor in enumerate(candidates, start=1)
        )
    return factors


def build_challenge_prompt(
    results: Sequence[DiseasePredictionResult],
    survey: MonthlyHealthSurvey | None,
    count: int,
) -> ChallengePrompt:
    if not results:
        raise ValueError("Disease prediction results are required to build a challenge prompt.")

    ordered = _sorted(results)
    factors = select_basis_factors(ordered)
    diseases = tuple(result.model_type for result in ordered)
    lines = [f"아래 분석 결과를 보고 챌린지 {count}개를 추천해 주세요.", "", "[질환별 위험도]"]
    lines.extend(
        f"- {result.model_type.label}({result.model_type}): 위험 등급 {result.risk_level.label}"
        f"({result.risk_level}), 위험도 {float(result.risk_score):.0f}%"
        for result in ordered
    )

    lines += ["", "[근거로 쓸 수 있는 요인] (질환별로 위험을 높인 순서)"]
    if factors:
        lines.extend(
            f"- feature: {factor.feature} | 표시명: {factor.display_name} | 현재 값: {_format_value(factor.value)}"
            f" | 질환: {factor.model_type} | 순위: {factor.rank}"
            for factor in factors
        )
    else:
        lines.append("- (없음: 생활습관으로 바꿀 수 있는 위험 요인이 확인되지 않았습니다)")
    distinct_features = len(dict.fromkeys(factor.feature for factor in factors))
    if 0 < distinct_features < count:
        lines.append(
            f"- 근거 요인이 {distinct_features}개라, 챌린지 {count - distinct_features}개까지는 "
            "basis_features를 비운 일반 건강 습관으로 채울 수 있습니다."
        )

    lines += ["", "[현재 생활습관]", *_habit_lines(survey)]
    if any(result.risk_level is DiseaseRiskLevel.HIGH for result in ordered):
        lines += ["", "위험 등급이 높은 질환이 있으므로, 의료진 상담을 권하는 문장을 description에 1문장 넣어 주세요."]

    return ChallengePrompt(
        system=SYSTEM_PROMPT,
        user="\n".join(lines),
        schema=build_output_schema([factor.feature for factor in factors], diseases),
        basis_factors=tuple(factors),
        target_diseases=diseases,
        count=count,
    )


def build_retry_message(prompt: ChallengePrompt, reasons: Sequence[str]) -> str:
    """앞선 응답이 검증을 통과하지 못했을 때, 사유를 붙여 다시 요청할 user 메시지입니다."""
    detail = "\n".join(f"- {reason}" for reason in reasons[:10])
    return f"{prompt.user}\n\n[이전 응답의 문제]\n{detail}\n위 문제를 고쳐 규칙에 맞게 다시 작성해 주세요."


def build_output_schema(features: Sequence[str], diseases: Sequence[PredictionModelType]) -> dict[str, Any]:
    """
    Structured outputs용 JSON 스키마입니다.
    Claude는 minLength·maxLength·maxItems·minimum 같은 제약을 지원하지 않으므로, 길이·개수·범위는 파서에서 검증합니다.
    feature·질환은 enum으로 제한해 목록 밖의 값을 처음부터 막습니다.
    """
    basis_items: dict[str, Any] = {"type": "string"}
    if features:
        basis_items["enum"] = list(dict.fromkeys(features))
    return {
        "type": "object",
        "properties": {
            "challenges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": f"{TITLE_MAX_LENGTH}자 이내"},
                        "description": {"type": "string", "description": f"{DESCRIPTION_MAX_LENGTH}자 이내"},
                        "challenge_type": {"type": "string", "enum": [str(item) for item in ChallengeType]},
                        "total_rounds": {"type": "integer", "description": "challenge_type별 목표 회차"},
                        "expected_effect": {"type": "string", "description": f"{EXPECTED_EFFECT_MAX_LENGTH}자 이내"},
                        "target_diseases": {
                            "type": "array",
                            "items": {"type": "string", "enum": [str(disease) for disease in diseases]},
                        },
                        "basis_features": {"type": "array", "items": basis_items},
                    },
                    "required": [
                        "title",
                        "description",
                        "challenge_type",
                        "total_rounds",
                        "expected_effect",
                        "target_diseases",
                        "basis_features",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["challenges"],
        "additionalProperties": False,
    }


def _sorted(results: Sequence[DiseasePredictionResult]) -> list[DiseasePredictionResult]:
    order = {model_type: index for index, model_type in enumerate(PredictionModelType)}
    return sorted(results, key=lambda result: order[result.model_type])


def _format_value(value: Any) -> str:
    if value is None:
        return "알 수 없음"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _habit_lines(survey: MonthlyHealthSurvey | None) -> list[str]:
    if survey is None:
        return ["- 월간 설문 정보 없음"]
    smoking = survey.smoking_status.label
    if survey.smoking_status is HabitStatus.CURRENT and survey.smoking_fr_per_day:
        smoking += f" (하루 {survey.smoking_fr_per_day}개비)"
    drinking = survey.drinking_status.label
    frequency = survey.drinking_frequency
    if (
        survey.drinking_status is HabitStatus.CURRENT
        and frequency is not None
        and frequency is not DrinkingFrequency.NOT_APPLICABLE
    ):
        amount = f", 1회 {survey.drinking_amount_per_session}잔" if survey.drinking_amount_per_session else ""
        drinking += f" ({frequency.label}{amount})"
    return [f"- 흡연: {smoking}", f"- 음주: {drinking}"]
