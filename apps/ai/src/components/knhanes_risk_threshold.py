"""
보정된 확률로 LOW·MODERATE·HIGH 위험 등급의 경계 2개를 정합니다.

- MODERATE 경계: 재현율(양성 중 MODERATE 이상 비율)이 최소 재현율 이상인 가장 높은 확률
- HIGH 경계: 특이도(음성 중 HIGH 미만 비율)가 최소 특이도 이상인 가장 낮은 확률
- 확률이 경계 이상이면 해당 등급 이상입니다.
"""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.components.knhanes_multi_year_loader import KnhanesDataValidationError

RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MODERATE = "MODERATE"
RISK_LEVEL_HIGH = "HIGH"


@dataclass(frozen=True)
class RiskThresholds:
    moderate: float
    high: float

    def __post_init__(self) -> None:
        if not 0 <= self.moderate <= self.high <= 1:
            raise ValueError(f"Risk thresholds must satisfy 0 <= moderate <= high <= 1: {self}")

    def classify(self, prob: np.ndarray) -> np.ndarray:
        prob = np.asarray(prob, dtype=float)
        if np.isnan(prob).any():
            raise KnhanesDataValidationError("prob must not contain NaN")
        return np.where(
            prob >= self.high, RISK_LEVEL_HIGH, np.where(prob >= self.moderate, RISK_LEVEL_MODERATE, RISK_LEVEL_LOW)
        )

    def to_dict(self) -> dict[str, float]:
        return {"moderate": self.moderate, "high": self.high}


@dataclass(frozen=True)
class ThresholdPerformance:
    level: str
    threshold: float
    recall: float
    specificity: float
    precision: float
    flagged_rate: float


@dataclass(frozen=True)
class ThresholdInterval:
    level: str
    threshold: float
    ci_lower: float
    ci_upper: float


def find_risk_thresholds(
    y_true: pd.Series | np.ndarray, prob: np.ndarray, min_recall: float, min_specificity: float
) -> RiskThresholds:
    labels, prob = _validate(y_true, prob)
    if not 0 < min_recall <= 1 or not 0 < min_specificity <= 1:
        raise ValueError("min_recall and min_specificity must be in (0, 1]")

    positives = np.sort(prob[labels == 1])[::-1]
    negatives = np.sort(prob[labels == 0])

    # 양성 확률을 내림차순으로 놓고 필요한 양성 수번째 값을 경계로 두면 그 이상이 재현율을 만족합니다.
    required_positives = math.ceil(min_recall * len(positives))
    moderate = float(positives[required_positives - 1])

    # 음성 중 필요한 수가 경계 미만이 되도록, 그 마지막 음성 확률보다 큰 가장 작은 값을 경계로 둡니다.
    required_negatives = math.ceil(min_specificity * len(negatives))
    high = float(np.nextafter(negatives[required_negatives - 1], np.inf))
    high = min(high, 1.0)

    # 성능이 매우 좋으면 HIGH 경계가 MODERATE 경계보다 낮아질 수 있습니다. 이때 MODERATE 구간은 비게 됩니다.
    return RiskThresholds(moderate=moderate, high=max(high, moderate))


def evaluate_thresholds(
    y_true: pd.Series | np.ndarray, prob: np.ndarray, thresholds: RiskThresholds
) -> list[ThresholdPerformance]:
    labels, prob = _validate(y_true, prob)
    results = []
    for level, threshold in [(RISK_LEVEL_MODERATE, thresholds.moderate), (RISK_LEVEL_HIGH, thresholds.high)]:
        flagged = prob >= threshold
        true_positive = int((flagged & (labels == 1)).sum())
        results.append(
            ThresholdPerformance(
                level=level,
                threshold=threshold,
                recall=true_positive / int((labels == 1).sum()),
                specificity=int((~flagged & (labels == 0)).sum()) / int((labels == 0).sum()),
                precision=true_positive / int(flagged.sum()) if flagged.any() else 0.0,
                flagged_rate=float(flagged.mean()),
            )
        )
    return results


@dataclass(frozen=True)
class ThresholdConfusion:
    """경계 이상을 양성으로 판정했을 때의 혼동 행렬과 지표입니다."""

    level: str
    threshold: float
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    specificity: float
    f1: float

    @classmethod
    def from_counts(
        cls,
        level: str,
        threshold: float,
        true_positive: int,
        false_positive: int,
        true_negative: int,
        false_negative: int,
    ) -> "ThresholdConfusion":
        if min(true_positive, false_positive, true_negative, false_negative) < 0:
            raise KnhanesDataValidationError("Confusion counts must not be negative")
        flagged = true_positive + false_positive
        positives = true_positive + false_negative
        negatives = true_negative + false_positive
        precision = true_positive / flagged if flagged else 0.0
        recall = true_positive / positives if positives else 0.0
        return cls(
            level=level,
            threshold=threshold,
            true_positive=true_positive,
            false_positive=false_positive,
            true_negative=true_negative,
            false_negative=false_negative,
            precision=precision,
            recall=recall,
            specificity=true_negative / negatives if negatives else 0.0,
            f1=2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        )


def threshold_confusions(
    y_true: pd.Series | np.ndarray, prob: np.ndarray, thresholds: RiskThresholds
) -> list[ThresholdConfusion]:
    """MODERATE·HIGH 경계 각각을 양성 판정 기준으로 쓸 때의 혼동 행렬입니다."""
    labels, prob = _validate(y_true, prob)
    results = []
    for level, threshold in [(RISK_LEVEL_MODERATE, thresholds.moderate), (RISK_LEVEL_HIGH, thresholds.high)]:
        flagged = prob >= threshold
        results.append(
            ThresholdConfusion.from_counts(
                level,
                threshold,
                true_positive=int((flagged & (labels == 1)).sum()),
                false_positive=int((flagged & (labels == 0)).sum()),
                true_negative=int((~flagged & (labels == 0)).sum()),
                false_negative=int((~flagged & (labels == 1)).sum()),
            )
        )
    return results


def confusion_from_threshold_performance(
    rows: int, positive_rate: float, performance: dict[str, float]
) -> ThresholdConfusion:
    """
    저장된 보고서의 행 수·양성률·재현율·특이도로 혼동 행렬을 복원합니다.
    이미 사용한 Test를 다시 예측하지 않고 지표를 보강하기 위한 함수입니다.
    복원한 행렬의 정밀도·해당 비율이 보고서 값과 다르면 거부합니다.
    """
    positives = round(rows * positive_rate)
    negatives = rows - positives
    true_positive = round(performance["recall"] * positives)
    true_negative = round(performance["specificity"] * negatives)
    confusion = ThresholdConfusion.from_counts(
        str(performance["level"]),
        float(performance["threshold"]),
        true_positive=true_positive,
        false_positive=negatives - true_negative,
        true_negative=true_negative,
        false_negative=positives - true_positive,
    )
    flagged_rate = (confusion.true_positive + confusion.false_positive) / rows
    if not np.isclose(confusion.precision, performance["precision"], atol=1e-9) or not np.isclose(
        flagged_rate, performance["flagged_rate"], atol=1e-9
    ):
        raise KnhanesDataValidationError(f"{performance['level']}: report values are not consistent")
    return confusion


def bootstrap_risk_thresholds(
    y_true: pd.Series | np.ndarray,
    prob: np.ndarray,
    households: pd.Series,
    min_recall: float,
    min_specificity: float,
    iterations: int,
    confidence_level: float,
    random_state: int,
) -> list[ThresholdInterval]:
    """가구 단위로 다시 뽑아 경계값이 표본에 따라 얼마나 흔들리는지 신뢰구간으로 보고합니다."""
    labels, prob = _validate(y_true, prob)
    if len(households) != len(labels):
        raise KnhanesDataValidationError("households and y_true must have the same length")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    household_codes = pd.factorize(households)[0]
    household_count = int(household_codes.max()) + 1
    generator = np.random.default_rng(random_state)

    moderates: list[float] = []
    highs: list[float] = []
    for _ in range(iterations):
        sampled = generator.integers(0, household_count, household_count)
        row_counts = np.bincount(sampled, minlength=household_count)[household_codes]
        sampled_rows = np.repeat(np.arange(len(labels)), row_counts)
        sampled_labels = labels[sampled_rows]
        if sampled_labels.min() == sampled_labels.max():
            continue
        thresholds = find_risk_thresholds(sampled_labels, prob[sampled_rows], min_recall, min_specificity)
        moderates.append(thresholds.moderate)
        highs.append(thresholds.high)

    if not moderates:
        raise KnhanesDataValidationError("Bootstrap samples never contained both classes")

    point = find_risk_thresholds(labels, prob, min_recall, min_specificity)
    tail = (1 - confidence_level) / 2 * 100
    intervals = []
    for level, threshold, values in [
        (RISK_LEVEL_MODERATE, point.moderate, moderates),
        (RISK_LEVEL_HIGH, point.high, highs),
    ]:
        ci_lower, ci_upper = np.percentile(values, [tail, 100 - tail])
        intervals.append(ThresholdInterval(level, threshold, float(ci_lower), float(ci_upper)))
    return intervals


def _validate(y_true: pd.Series | np.ndarray, prob: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(y_true)
    prob = np.asarray(prob, dtype=float)
    if len(labels) != len(prob):
        raise KnhanesDataValidationError("y_true and prob must have the same length")
    if not np.isin(labels, [0, 1]).all() or len(np.unique(labels)) != 2:
        raise KnhanesDataValidationError("y_true must contain both 0 and 1 only")
    if np.isnan(prob).any() or (prob < 0).any() or (prob > 1).any():
        raise KnhanesDataValidationError("prob must be between 0 and 1")
    return labels.astype(int), prob
