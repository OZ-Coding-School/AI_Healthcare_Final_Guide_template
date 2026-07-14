from enum import StrEnum


class Gender(StrEnum):
    MALE = "M"
    FEMALE = "F"


class HabitStatus(StrEnum):
    NEVER = "NEVER"  # Never smoked
    FORMER = "FORMER"  # Smoked before
    CURRENT = "CURRENT"  # Currently smoking


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


class DiseaseRiskLevel(StrEnum):
    LOW = "LOW"  # Low risk(30% 이하)
    MODERATE = "MODERATE"  # Moderate risk(31%이상, 60%이하)
    HIGH = "HIGH"  # High risk(61이상, 100%이하)


class ChallengeType(StrEnum):
    DAILY = "DAILY"  # Daily challenge
    WEEKLY = "WEEKLY"  # Weekly challenge
    MONTHLY = "MONTHLY"  # Monthly challenge
    COUNT_BASED = "COUNT_BASED"  # Count-based challenge


class ChallengeStatus(StrEnum):
    PENDING = "PENDING"  # Challenge pending approval
    IN_PROGRESS = "IN_PROGRESS"  # Challenge in progress
    COMPLETED = "COMPLETED"  # Challenge completed
    FAILED = "FAILED"  # Challenge failed
    ABANDONED = "ABANDONED"  # Challenge abandoned (because, challenge is expired)


class ExerciseType(StrEnum):
    CARDIO = "CARDIO"  # 유산소
    STRENGTH = "STRENGTH"  # 근력
    BOTH = "BOTH"  # 유산소, 근력 둘다
    NOT_APPLICABLE = "NOT_APPLICABLE"  # 해당사항 없음


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


class UrineProteinStatus(StrEnum):
    NEGATIVE = "-"
    TRACE = "±"
    POSITIVE_1 = "1+"
    POSITIVE_2 = "2+"
    POSITIVE_3 = "3+"
    POSITIVE_4 = "4+"

    @property
    def description(self) -> str:
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
    def status_message(self) -> str:
        """임상적 상태 메시지"""
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
    def description(self) -> str:
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
    def status(self) -> str:
        """임상적 상태 메시지"""
        mapping = {
            UrineGlucoseStatus.NEGATIVE: "정상 (소변에 당이 없음)",
            UrineGlucoseStatus.TRACE: "추적 관찰 필요 (일시적 당뇨 가능성)",
            UrineGlucoseStatus.POSITIVE_1: "정밀 검사 필요 (당뇨 의심 수치)",
            UrineGlucoseStatus.POSITIVE_2: "고혈당 의심 (추가 혈당 검사 필요)",
            UrineGlucoseStatus.POSITIVE_3: "당뇨병 가능성 매우 높음",
            UrineGlucoseStatus.POSITIVE_4: "중증 고혈당 및 신장 여과 기능 이상",
        }
        return mapping[self]
