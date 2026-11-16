from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.repositories.monthly_health_survey_repository import month_bounds


@pytest.mark.parametrize(
    ("moment", "expected_start", "expected_next_start"),
    [
        # 30일까지인 달의 말일 (기존 코드는 day=31에서 ValueError)
        (datetime(2026, 11, 30, 23, 59, 59), datetime(2026, 11, 1), datetime(2026, 12, 1)),
        (datetime(2026, 4, 15, 9, 0), datetime(2026, 4, 1), datetime(2026, 5, 1)),
        # 2월 (평년·윤년)
        (datetime(2026, 2, 28, 12, 0), datetime(2026, 2, 1), datetime(2026, 3, 1)),
        (datetime(2028, 2, 29, 12, 0), datetime(2028, 2, 1), datetime(2028, 3, 1)),
        # 31일까지인 달
        (datetime(2026, 1, 31, 0, 0), datetime(2026, 1, 1), datetime(2026, 2, 1)),
        # 12월: 다음 달 시작이 다음 해 1월 1일
        (datetime(2026, 12, 31, 23, 59, 59, 999999), datetime(2026, 12, 1), datetime(2027, 1, 1)),
        # 1일 0시 정각
        (datetime(2026, 11, 1, 0, 0), datetime(2026, 11, 1), datetime(2026, 12, 1)),
    ],
)
def test_month_bounds_covers_whole_month(
    moment: datetime, expected_start: datetime, expected_next_start: datetime
) -> None:
    start, next_start = month_bounds(moment)

    assert start == expected_start
    assert next_start == expected_next_start
    assert start <= moment < next_start


def test_month_bounds_keeps_timezone() -> None:
    seoul = ZoneInfo("Asia/Seoul")
    start, next_start = month_bounds(datetime(2026, 11, 30, 10, 0, tzinfo=seoul))

    assert start == datetime(2026, 11, 1, tzinfo=seoul)
    assert next_start == datetime(2026, 12, 1, tzinfo=seoul)
