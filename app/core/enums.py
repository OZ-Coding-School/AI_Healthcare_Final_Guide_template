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
    CARDIO = "CARDIO"
    STRENGTH = "STRENGTH"
    BOTH = "BOTH"
    NOT_APPLICABLE = "NOT_APPLICABLE"


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
