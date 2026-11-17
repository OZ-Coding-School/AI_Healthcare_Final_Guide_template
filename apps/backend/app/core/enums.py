from enum import StrEnum


class Gender(StrEnum):
    MALE = "M"
    FEMALE = "F"

    @property
    def label(self) -> str:
        mapping = {
            Gender.MALE: "남자",
            Gender.FEMALE: "여자",
        }
        return mapping[self]


class HabitStatus(StrEnum):
    NEVER = "NEVER"  # Never smoked
    FORMER = "FORMER"  # Smoked before
    CURRENT = "CURRENT"  # Currently smoking

    @property
    def label(self) -> str:
        mapping = {
            HabitStatus.NEVER: "전혀 없음",
            HabitStatus.FORMER: "이전 경험은 있지만, 현재는 하지않음",
            HabitStatus.CURRENT: "하고 있음",
        }
        return mapping[self]


class DrinkingFrequency(StrEnum):
    LESS_THAN_MONTHLY = "LESS_THAN_MONTHLY"  # 월 1회 미만
    MONTHLY = "MONTHLY"  # 월 1회 정도
    MONTHLY_2_TO_4 = "MONTHLY_2_TO_4"  # 월 2~4회
    WEEKLY_2_TO_3 = "WEEKLY_2_TO_3"  # 주 2~3회
    WEEKLY_4_OR_MORE = "WEEKLY_4_OR_MORE"  # 주 4회 이상
    NOT_APPLICABLE = "NOT_APPLICABLE"  # 해당없음

    @property
    def label(self) -> str:
        mapping = {
            DrinkingFrequency.LESS_THAN_MONTHLY: "월 1회 미만",
            DrinkingFrequency.MONTHLY: "월 1회 정도",
            DrinkingFrequency.MONTHLY_2_TO_4: "월 2~4회",
            DrinkingFrequency.WEEKLY_2_TO_3: "주 2~3회",
            DrinkingFrequency.WEEKLY_4_OR_MORE: "주 4회 이상",
            DrinkingFrequency.NOT_APPLICABLE: "해당없음",
        }
        return mapping[self]


class BloodSugarMeasurementType(StrEnum):
    FASTING = "FASTING"  # 공복
    BEFORE_BREAKFAST = "BEFORE_BREAKFAST"  # 아침 식전
    AFTER_BREAKFAST = "AFTER_BREAKFAST"  # 아침 식후
    BEFORE_LUNCH = "BEFORE_LUNCH"  # 점심 식전
    AFTER_LUNCH = "AFTER_LUNCH"  # 점심 식후
    BEFORE_DINNER = "BEFORE_DINNER"  # 저녁 식전
    AFTER_DINNER = "AFTER_DINNER"  # 저녁 식후
    BEFORE_SLEEP = "BEFORE_SLEEP"  # 취침전
    RANDOM = "RANDOM"  # 임의측정

    @property
    def label(self) -> str:
        mapping = {
            BloodSugarMeasurementType.FASTING: "공복",
            BloodSugarMeasurementType.BEFORE_BREAKFAST: "아침 식전",
            BloodSugarMeasurementType.AFTER_BREAKFAST: "아침 식후",
            BloodSugarMeasurementType.BEFORE_LUNCH: "점심 식전",
            BloodSugarMeasurementType.AFTER_LUNCH: "점심 식후",
            BloodSugarMeasurementType.BEFORE_DINNER: "저녁 식전",
            BloodSugarMeasurementType.AFTER_DINNER: "저녁 식후",
            BloodSugarMeasurementType.BEFORE_SLEEP: "취침전",
            BloodSugarMeasurementType.RANDOM: "임의측정",
        }
        return mapping[self]


# 등급 경계는 고정값이 아니라 모델마다 서빙 번들의 thresholds.json(moderate, high)으로 정해집니다.
class DiseaseRiskLevel(StrEnum):
    LOW = "LOW"  # 위험도 < moderate 경계
    MODERATE = "MODERATE"  # moderate 경계 ≤ 위험도 < high 경계
    HIGH = "HIGH"  # 위험도 ≥ high 경계

    @property
    def label(self) -> str:
        mapping = {
            DiseaseRiskLevel.LOW: "낮음",
            DiseaseRiskLevel.MODERATE: "중간",
            DiseaseRiskLevel.HIGH: "높음",
        }
        return mapping[self]


class DiseasePredictionStatus(StrEnum):
    # 정상: PENDING → PROCESSING → COMPLETED, 비정상: PENDING → PROCESSING → FAILED
    # (요청 발행 실패·결과 만료처럼 Worker가 가져가기 전에 끝나면 PENDING → FAILED)
    PENDING = "PENDING"  # AI Worker가 Task를 가져가기를 기다리는 중
    PROCESSING = "PROCESSING"  # AI Worker가 추론 중
    COMPLETED = "COMPLETED"  # 예측 완료
    FAILED = "FAILED"  # 예측 실패

    @property
    def label(self) -> str:
        mapping = {
            DiseasePredictionStatus.PENDING: "대기 중",
            DiseasePredictionStatus.PROCESSING: "분석 중",
            DiseasePredictionStatus.COMPLETED: "분석 완료",
            DiseasePredictionStatus.FAILED: "분석 실패",
        }
        return mapping[self]

    @classmethod
    def in_progress(cls) -> tuple["DiseasePredictionStatus", ...]:
        """아직 결과가 확정되지 않은 상태입니다."""
        return (cls.PENDING, cls.PROCESSING)


class PredictionModelType(StrEnum):
    # 값은 AI Worker 결과의 model_type과 같아야 합니다.
    DIABETES_RISK = "diabetes_risk"
    HYPERTENSION_RISK = "hypertension_risk"

    @property
    def label(self) -> str:
        mapping = {
            PredictionModelType.DIABETES_RISK: "당뇨병",
            PredictionModelType.HYPERTENSION_RISK: "고혈압",
        }
        return mapping[self]


class FamilyHistoryAnswer(StrEnum):
    YES = "YES"  # 병력 있음
    NO = "NO"  # 병력 없음
    UNKNOWN = "UNKNOWN"  # 모름
    NO_SIBLINGS = "NO_SIBLINGS"  # 형제자매 없음 (형제자매 항목에만 허용)

    @property
    def label(self) -> str:
        mapping = {
            FamilyHistoryAnswer.YES: "있음",
            FamilyHistoryAnswer.NO: "없음",
            FamilyHistoryAnswer.UNKNOWN: "모름",
            FamilyHistoryAnswer.NO_SIBLINGS: "형제자매 없음",
        }
        return mapping[self]


class ChallengeType(StrEnum):
    DAILY = "DAILY"  # Daily challenge
    WEEKLY = "WEEKLY"  # Weekly challenge
    MONTHLY = "MONTHLY"  # Monthly challenge
    COUNT_BASED = "COUNT_BASED"  # Count-based challenge

    @property
    def label(self) -> str:
        mapping = {
            ChallengeType.DAILY: "일일 챌린지",
            ChallengeType.WEEKLY: "주간 챌린지",
            ChallengeType.MONTHLY: "월간 챌린지",
            ChallengeType.COUNT_BASED: "횟수형 챌린지",
        }
        return mapping[self]


class ChallengeStatus(StrEnum):
    PENDING = "PENDING"  # Challenge pending approval
    IN_PROGRESS = "IN_PROGRESS"  # Challenge in progress
    COMPLETED = "COMPLETED"  # Challenge completed
    FAILED = "FAILED"  # Challenge failed
    ABANDONED = "ABANDONED"  # Challenge abandoned (because, challenge is expired)

    @property
    def label(self) -> str:
        mapping = {
            ChallengeStatus.PENDING: "대기중",
            ChallengeStatus.IN_PROGRESS: "진행중",
            ChallengeStatus.COMPLETED: "완료",
            ChallengeStatus.FAILED: "실패",
            ChallengeStatus.ABANDONED: "포기",
        }
        return mapping[self]


class ExerciseType(StrEnum):
    CARDIO = "CARDIO"  # 유산소
    STRENGTH = "STRENGTH"  # 근력
    BOTH = "BOTH"  # 유산소, 근력 둘다
    NOT_APPLICABLE = "NOT_APPLICABLE"  # 해당사항 없음

    @property
    def label(self) -> str:
        mapping = {
            ExerciseType.CARDIO: "유산소",
            ExerciseType.STRENGTH: "근력",
            ExerciseType.BOTH: "유산소, 근력",
            ExerciseType.NOT_APPLICABLE: "해당사항 없음",
        }
        return mapping[self]


class WithdrawalReason(StrEnum):
    NOT_USE = "NOT_USE"  # 더이상 사용하지 않음
    INCONVENIENT = "INCONVENIENT"  # 불편함
    LACK_OF_FEATURES = "LACK_OF_FEATURES"  # 기능 부족
    BUG_OR_ERROR = "BUG_OR_ERROR"  # 버그 또는 오류
    FOUND_ALTERNATIVE = "FOUND_ALTERNATIVE"  # 다른 앱을 찾음
    GOAL_ACHIEVED = "GOAL_ACHIEVED"  # 건강 목표를 달성함
    PRIVACY_CONCERN = "PRIVACY_CONCERN"  # 개인정보 보호
    TOO_MANY_NOTIFICATIONS = "TOO_MANY_NOTIFICATIONS"  # 알림이 너무 많음
    OTHER = "OTHER"  # 기타

    @property
    def label(self) -> str:
        mapping = {
            WithdrawalReason.NOT_USE: "더이상 사용하지 않음",
            WithdrawalReason.INCONVENIENT: "서비스 이용이 불편함",
            WithdrawalReason.LACK_OF_FEATURES: "서비스의 기능이 부족함",
            WithdrawalReason.BUG_OR_ERROR: "버그 또는 오류",
            WithdrawalReason.FOUND_ALTERNATIVE: "다른 유용한 앱을 찾음",
            WithdrawalReason.GOAL_ACHIEVED: "건강 목표를 달성함",
            WithdrawalReason.PRIVACY_CONCERN: "개인정보 보호",
            WithdrawalReason.TOO_MANY_NOTIFICATIONS: "알림이 너무 많음",
            WithdrawalReason.OTHER: "기타",
        }
        return mapping[self]


class UrineProteinStatus(StrEnum):
    NEGATIVE = "-"
    TRACE = "±"
    POSITIVE_1 = "1+"
    POSITIVE_2 = "2+"
    POSITIVE_3 = "3+"
    POSITIVE_4 = "4+"

    @property
    def label(self) -> str:
        """한글 명칭"""
        mapping = {
            UrineProteinStatus.NEGATIVE: "음성",
            UrineProteinStatus.TRACE: "약양성(흔적)",
            UrineProteinStatus.POSITIVE_1: "양성(1+)",
            UrineProteinStatus.POSITIVE_2: "양성(2+)",
            UrineProteinStatus.POSITIVE_3: "양성(3+)",
            UrineProteinStatus.POSITIVE_4: "양성(4+)",
        }
        return mapping[self]

    @property
    def description(self) -> str:
        """임상적 상태 설명"""
        mapping = {
            UrineProteinStatus.NEGATIVE: "정상 상태",
            UrineProteinStatus.TRACE: "추적 관찰 필요 단계",
            UrineProteinStatus.POSITIVE_1: "단백뇨 의심 단계",
            UrineProteinStatus.POSITIVE_2: "정밀검사 필요 단계",
            UrineProteinStatus.POSITIVE_3: "신장 질환 가능성이 높은 단계",
            UrineProteinStatus.POSITIVE_4: "심각한 신장 손상 위험 단계",
        }
        return mapping[self]


class UrineGlucoseStatus(StrEnum):
    NEGATIVE = "-"
    TRACE = "±"
    POSITIVE_1 = "1+"
    POSITIVE_2 = "2+"
    POSITIVE_3 = "3+"
    POSITIVE_4 = "4+"

    @property
    def label(self) -> str:
        """한글 명칭"""
        mapping = {
            UrineGlucoseStatus.NEGATIVE: "음성",
            UrineGlucoseStatus.TRACE: "약양성(흔적)",
            UrineGlucoseStatus.POSITIVE_1: "양성(1+)",
            UrineGlucoseStatus.POSITIVE_2: "양성(2+)",
            UrineGlucoseStatus.POSITIVE_3: "양성(3+)",
            UrineGlucoseStatus.POSITIVE_4: "양성(4+)",
        }
        return mapping[self]

    @property
    def description(self) -> str:
        """임상적 상태 설명"""
        mapping = {
            UrineGlucoseStatus.NEGATIVE: "정상 (소변에 당이 없음)",
            UrineGlucoseStatus.TRACE: "추적 관찰 필요 (일시적 당뇨 가능성)",
            UrineGlucoseStatus.POSITIVE_1: "정밀 검사 필요 (당뇨 의심 수치)",
            UrineGlucoseStatus.POSITIVE_2: "고혈당 의심 (추가 혈당 검사 필요)",
            UrineGlucoseStatus.POSITIVE_3: "당뇨병 가능성 매우 높음",
            UrineGlucoseStatus.POSITIVE_4: "중증 고혈당 및 신장 여과 기능 이상",
        }
        return mapping[self]
