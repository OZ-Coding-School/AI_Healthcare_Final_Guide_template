from datetime import date, timedelta

import pytest

from app.core.enums import ChallengeStatus, ChallengeType
from app.services.challenge_progress import HistoryEntry, calculate_progress, required_success_count

JOINED = date(2026, 11, 1)
RATE = 0.8
COUNT_DAYS = 30


def day(offset: int) -> date:
    return JOINED + timedelta(days=offset)


def entry(current_round: int, is_success: bool = True, offset: int = 0) -> HistoryEntry:
    return HistoryEntry(current_round=current_round, is_success=is_success, recorded_on=day(offset))


def progress(challenge_type: ChallengeType, total: int, today_offset: int, histories: list[HistoryEntry] | None = None):
    return calculate_progress(challenge_type, total, JOINED, day(today_offset), histories or [], RATE, COUNT_DAYS)


# ---------- 필요한 성공 회차 ----------


@pytest.mark.parametrize(
    ("total", "expected"),
    [(14, 12), (10, 8), (5, 4), (3, 3), (1, 1), (21, 17)],
)
def test_required_success_rounds_up(total: int, expected: int) -> None:
    assert required_success_count(ChallengeType.DAILY, total, RATE) == expected


def test_required_success_avoids_float_error() -> None:
    # 0.7 × 10 = 7.000000000000001 이지만 8이 아니라 7이어야 합니다.
    assert required_success_count(ChallengeType.WEEKLY, 10, 0.7) == 7


def test_count_based_requires_all_rounds() -> None:
    assert required_success_count(ChallengeType.COUNT_BASED, 10, RATE) == 10


# ---------- 주기형 회차 계산 ----------


@pytest.mark.parametrize(
    ("challenge_type", "today_offset", "expected_round"),
    [
        (ChallengeType.DAILY, 0, 1),
        (ChallengeType.DAILY, 3, 4),
        (ChallengeType.WEEKLY, 6, 1),
        (ChallengeType.WEEKLY, 7, 2),
        (ChallengeType.MONTHLY, 29, 1),
        (ChallengeType.MONTHLY, 30, 2),
    ],
)
def test_current_round_follows_period_length(
    challenge_type: ChallengeType, today_offset: int, expected_round: int
) -> None:
    # 목표 회차를 넉넉히 둡니다. 적으면 지나간 회차 때문에 80%를 채울 수 없어 조기 실패로 판정됩니다.
    result = progress(challenge_type, 30, today_offset)

    assert result.current_round == expected_round
    assert result.can_record is True
    assert result.outcome is None


def test_ends_on_is_last_day_of_period() -> None:
    assert progress(ChallengeType.DAILY, 14, 0).ends_on == day(13)
    assert progress(ChallengeType.WEEKLY, 4, 0).ends_on == day(27)
    assert progress(ChallengeType.MONTHLY, 2, 0).ends_on == day(59)


def test_recorded_round_cannot_be_recorded_again() -> None:
    result = progress(ChallengeType.DAILY, 14, 2, [entry(3)])

    assert result.can_record is False
    assert result.current_round is None
    assert result.success_count == 1
    assert result.recorded_count == 1


def test_failed_record_counts_as_recorded_but_not_success() -> None:
    result = progress(ChallengeType.DAILY, 14, 0, [entry(1, is_success=False)])

    assert result.recorded_count == 1
    assert result.success_count == 0
    assert result.can_record is False


# ---------- 주기형 판정 ----------


def test_periodic_completes_when_last_round_is_recorded_with_enough_success() -> None:
    # 5회차 중 4회 성공(80%), 4회차는 건너뜀
    histories = [entry(1), entry(2), entry(3), entry(5)]

    result = progress(ChallengeType.DAILY, 5, 4, histories)

    assert result.outcome is ChallengeStatus.COMPLETED
    assert result.can_record is False


def test_periodic_fails_when_period_ends_below_rate() -> None:
    result = progress(ChallengeType.DAILY, 3, 5, [entry(1)])

    assert result.outcome is ChallengeStatus.FAILED


def test_periodic_completes_when_period_ends_at_rate() -> None:
    result = progress(ChallengeType.WEEKLY, 5, 40, [entry(1), entry(2), entry(3), entry(4)])

    assert result.outcome is ChallengeStatus.COMPLETED


def test_periodic_fails_early_when_rate_becomes_unreachable() -> None:
    # 5회차 중 4회 성공이 필요한데, 3일째까지 기록이 없으면 남은 3회를 모두 성공해도 3회입니다.
    result = progress(ChallengeType.DAILY, 5, 2)

    assert result.outcome is ChallengeStatus.FAILED


def test_periodic_keeps_going_while_rate_is_reachable() -> None:
    result = progress(ChallengeType.DAILY, 5, 1)

    assert result.outcome is None
    assert result.current_round == 2


def test_out_of_range_rounds_are_ignored() -> None:
    result = progress(ChallengeType.DAILY, 3, 0, [entry(4), entry(0)])

    assert result.success_count == 0
    assert result.recorded_count == 0


# ---------- 횟수형 ----------


def test_count_based_next_round_is_sequential() -> None:
    result = progress(ChallengeType.COUNT_BASED, 10, 3, [entry(1, offset=0), entry(2, offset=1)])

    assert result.current_round == 3
    assert result.can_record is True
    assert result.ends_on == day(29)


def test_count_based_allows_one_record_per_day() -> None:
    result = progress(ChallengeType.COUNT_BASED, 10, 1, [entry(1, offset=1)])

    assert result.can_record is False
    assert result.current_round is None
    assert result.outcome is None


def test_count_based_completes_immediately_when_target_reached() -> None:
    histories = [entry(1, offset=0), entry(2, offset=2), entry(3, offset=5)]

    result = progress(ChallengeType.COUNT_BASED, 3, 5, histories)

    assert result.outcome is ChallengeStatus.COMPLETED


def test_count_based_failure_does_not_count_toward_target() -> None:
    histories = [entry(1, offset=0), entry(2, is_success=False, offset=1)]

    result = progress(ChallengeType.COUNT_BASED, 3, 2, histories)

    assert result.success_count == 1
    assert result.recorded_count == 2
    assert result.current_round == 3


def test_count_based_fails_after_deadline() -> None:
    result = progress(ChallengeType.COUNT_BASED, 3, 30, [entry(1)])

    assert result.outcome is ChallengeStatus.FAILED


def test_count_based_fails_early_when_days_run_out() -> None:
    # 마지막 날(29일째)에 2회가 더 필요하면 하루 1회 제한으로 채울 수 없습니다.
    result = progress(ChallengeType.COUNT_BASED, 3, 29, [entry(1)])

    assert result.outcome is ChallengeStatus.FAILED


def test_count_based_last_day_is_still_recordable() -> None:
    result = progress(ChallengeType.COUNT_BASED, 3, 29, [entry(1, offset=0), entry(2, offset=1)])

    assert result.outcome is None
    assert result.can_record is True


def test_total_rounds_must_be_positive() -> None:
    with pytest.raises(ValueError):
        progress(ChallengeType.DAILY, 0, 0)
