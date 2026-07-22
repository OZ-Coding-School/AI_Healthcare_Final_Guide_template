from enum import StrEnum


class SmokingStatus(StrEnum):
    NEVER = "NEVER"
    FORMER = "FORMER"
    CURRENT = "CURRENT"


class DrinkingStatus(StrEnum):
    NEVER = "NEVER"
    FORMER = "FORMER"
    CURRENT = "CURRENT"


class DrinkingFrequency(StrEnum):
    LESS_THAN_MONTHLY = "LESS_THAN_MONTHLY" # 월 1회 미만
    MONTHLY = "MONTHLY"  # 월 1회 정도
    MONTHLY_2_TO_4 = "MONTHLY_2_TO_4"  # 월 2~4회
    WEEKLY_2_TO_3 = "WEEKLY_2_TO_3"  # 주 2~3회
    WEEKLY_4_OR_MORE = "WEEKLY_4_OR_MORE"  # 주 4회 이상
    NOT_APPLICABLE = "NOT_APPLICABLE" # 해당없음


class UrinalysisStatus(StrEnum):
    NEGATIVE = "-"
    TRACE = "±"
    POSITIVE_1 = "1+"
    POSITIVE_2 = "2+"
    POSITIVE_3 = "3+"
    POSITIVE_4 = "4+"
