"""
실제 Claude API로 챌린지 추천 경로를 한 번 점검합니다. DB·Redis 없이 실행됩니다.

서비스와 같은 순서로 실행합니다: 예시 예측 결과 → 프롬프트·JSON 스키마 생성 → Claude 호출 → 응답 검증.
API 키·모델·스키마(Structured outputs)가 실제 API에서 받아들여지는지 확인하는 용도이며, 테스트 코드에서는 실행하지 않습니다.

실행 (저장소 루트 .env에 ANTHROPIC_API_KEY를 넣고 fastapi 컨테이너를 다시 만든 뒤)
    docker compose up -d fastapi
    docker exec fastapi uv run --no-sync python -m app.scripts.check_llm_challenge

로컬에서 실행할 때는 apps/backend에서
    uv run --with tzdata python -m app.scripts.check_llm_challenge

종료 코드: 0 성공, 1 설정 오류(키 없음·요청 거절), 2 일시적 장애, 3 응답 검증 실패
API 키와 응답 본문 전체는 출력하지 않습니다.
"""

import asyncio
import sys
from decimal import Decimal

from app.core import settings
from app.core.enums import DiseaseRiskLevel, DrinkingFrequency, HabitStatus, PredictionModelType
from app.core.llm import LLMNotConfiguredError, LLMRequestError, LLMUnavailableError, get_llm_client
from app.models.disease_prediction_models import DiseasePredictionResult
from app.models.health_profiles import MonthlyHealthSurvey
from app.services.challenge_parser import ChallengeParseError, parse_challenges
from app.services.challenge_prompt import build_challenge_prompt


def _factor(feature: str, display_name: str, value: float, shap_value: float, actionable: bool = True) -> dict:
    return {
        "feature": feature,
        "display_name": display_name,
        "value": value,
        "shap_value": shap_value,
        "direction": "increase" if shap_value >= 0 else "decrease",
        "actionable": actionable,
        "reverse_causation_suspected": False,
    }


def sample_results() -> list[DiseasePredictionResult]:
    """실제 사용자 데이터 대신 쓰는 예시 예측 결과입니다 (DB에 저장하지 않음)."""
    return [
        DiseasePredictionResult(
            model_type=PredictionModelType.DIABETES_RISK,
            risk_level=DiseaseRiskLevel.MODERATE,
            risk_score=Decimal("23.46"),
            shap_results=[
                _factor("허리둘레", "허리둘레", 92.0, 0.0812),
                _factor("나이", "나이", 54, 0.0512, actionable=False),
                _factor("중성지방", "중성지방", 180, 0.031),
            ],
            out_of_training_range=[],
        ),
        DiseasePredictionResult(
            model_type=PredictionModelType.HYPERTENSION_RISK,
            risk_level=DiseaseRiskLevel.HIGH,
            risk_score=Decimal("67.89"),
            shap_results=[
                _factor("BMI", "체질량지수(BMI)", 26.2, 0.12),
                _factor("1년간 음주빈도", "음주 빈도", 4, 0.07),
            ],
            out_of_training_range=[],
        ),
    ]


def sample_survey() -> MonthlyHealthSurvey:
    return MonthlyHealthSurvey(
        title="점검용 설문",
        smoking_status=HabitStatus.NEVER,
        drinking_status=HabitStatus.CURRENT,
        drinking_frequency=DrinkingFrequency.WEEKLY_2_TO_3,
        drinking_amount_per_session=5,
        systolic_bp=135,
        diastolic_bp=88,
    )


async def main() -> int:
    prompt = build_challenge_prompt(sample_results(), sample_survey(), settings.CHALLENGE_RECOMMENDATION_COUNT)
    client = get_llm_client()
    print(
        f"[설정] 모델={client.model_name}, API 버전={settings.ANTHROPIC_API_VERSION}, URL={settings.ANTHROPIC_API_URL}"
    )
    print(f"[설정] API 키 설정 여부={'예' if settings.ANTHROPIC_API_KEY.get_secret_value() else '아니오'}")
    print(f"[프롬프트] 근거 요인={sorted(prompt.allowed_features)}")

    try:
        response = await client.generate_json(prompt.system, prompt.user, prompt.schema)
    except LLMNotConfiguredError:
        print("[실패] ANTHROPIC_API_KEY가 비어 있습니다. 루트 .env에 키를 넣고 컨테이너를 다시 만드세요.")
        return 1
    except LLMRequestError as error:
        print(f"[실패] 요청이 거절됐습니다: status={error.status_code}, type={error.error_type}")
        print("        401은 키 오류, 404는 모델 이름 오류, 400은 요청 형식(스키마) 오류일 가능성이 큽니다.")
        return 1
    except LLMUnavailableError as error:
        print(f"[실패] 일시적 장애입니다. 잠시 후 다시 실행하세요: {error}")
        return 2

    print(f"[응답] 모델={response.model}, stop_reason={response.stop_reason}, usage={response.usage}")
    try:
        challenges = parse_challenges(
            response.text,
            allowed_features=prompt.allowed_features,
            allowed_diseases={str(disease) for disease in prompt.target_diseases},
            max_count=prompt.count,
        )
    except ChallengeParseError as error:
        print("[실패] 응답이 검증을 통과하지 못했습니다.")
        for reason in error.reasons:
            print(f"        - {reason}")
        return 3

    print(f"[성공] 검증을 통과한 챌린지 {len(challenges)}개")
    for index, challenge in enumerate(challenges, start=1):
        print(f"  {index}. {challenge.title} ({challenge.challenge_type}, {challenge.total_rounds}회차)")
        print(f"     질환={challenge.target_diseases}, 근거={challenge.basis_features}")
        print(f"     기대 효과: {challenge.expected_effect}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
