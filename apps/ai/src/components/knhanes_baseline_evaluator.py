from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.components.knhanes_multi_year_loader import KnhanesDataValidationError


@dataclass(frozen=True)
class BaselineMetrics:
    rows: int
    positive_rate: float
    roc_auc: float
    pr_auc: float
    weighted_roc_auc: float
    brier: float
    mean_predicted: float


@dataclass(frozen=True)
class PairedDifference:
    metric: str
    reference: float
    compared: float
    difference: float
    ci_lower: float
    ci_upper: float

    @property
    def is_significant(self) -> bool:
        return self.ci_lower > 0 or self.ci_upper < 0


def compute_baseline_metrics(y_true: pd.Series, y_prob: np.ndarray, weights: pd.Series) -> BaselineMetrics:
    """
    임계값에 의존하지 않는 지표를 계산합니다. 임계값은 Calibration 이후 단계에서 정합니다.
    weighted_roc_auc는 표본 가중치를 적용한 값으로, 인구 대표성 확인용 보조 지표입니다.
    """
    _validate_labels_and_probabilities(y_true, y_prob)
    labels = y_true.to_numpy()

    return BaselineMetrics(
        rows=len(labels),
        positive_rate=float(labels.mean()),
        roc_auc=float(roc_auc_score(labels, y_prob)),
        pr_auc=float(average_precision_score(labels, y_prob)),
        weighted_roc_auc=float(roc_auc_score(labels, y_prob, sample_weight=weights.to_numpy())),
        brier=float(brier_score_loss(labels, y_prob)),
        mean_predicted=float(y_prob.mean()),
    )


def compare_paired_predictions(
    y_true: pd.Series,
    reference_prob: np.ndarray,
    compared_prob: np.ndarray,
    households: pd.Series,
    iterations: int,
    confidence_level: float,
    random_state: int,
) -> list[PairedDifference]:
    """
    같은 Validation 행에 대한 두 모델의 차이(reference - compared)를 가구 단위 부트스트랩으로 추정합니다.
    가구를 뽑아 행을 함께 묶어야 가족 간 유사성으로 신뢰구간이 좁아지지 않습니다.
    """
    _validate_labels_and_probabilities(y_true, reference_prob)
    _validate_labels_and_probabilities(y_true, compared_prob)
    if not len(y_true) == len(households):
        raise KnhanesDataValidationError("y_true and households must have the same length")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    labels = y_true.to_numpy()
    household_codes = pd.factorize(households)[0]
    household_count = int(household_codes.max()) + 1
    generator = np.random.default_rng(random_state)

    roc_differences: list[float] = []
    pr_differences: list[float] = []
    for _ in range(iterations):
        sampled_households = generator.integers(0, household_count, household_count)
        row_weights = np.bincount(sampled_households, minlength=household_count)[household_codes]
        sampled_labels = labels[row_weights > 0]
        if sampled_labels.min() == sampled_labels.max():
            continue
        roc_differences.append(
            float(roc_auc_score(labels, reference_prob, sample_weight=row_weights))
            - float(roc_auc_score(labels, compared_prob, sample_weight=row_weights))
        )
        pr_differences.append(
            float(average_precision_score(labels, reference_prob, sample_weight=row_weights))
            - float(average_precision_score(labels, compared_prob, sample_weight=row_weights))
        )

    if not roc_differences:
        raise KnhanesDataValidationError("Bootstrap samples never contained both classes")

    tail = (1 - confidence_level) / 2 * 100
    results = []
    for metric, score_function, differences in [
        ("roc_auc", roc_auc_score, roc_differences),
        ("pr_auc", average_precision_score, pr_differences),
    ]:
        reference = float(score_function(labels, reference_prob))
        compared = float(score_function(labels, compared_prob))
        ci_lower, ci_upper = np.percentile(differences, [tail, 100 - tail])
        results.append(
            PairedDifference(
                metric=metric,
                reference=reference,
                compared=compared,
                difference=reference - compared,
                ci_lower=float(ci_lower),
                ci_upper=float(ci_upper),
            )
        )
    return results


def _validate_labels_and_probabilities(y_true: pd.Series, y_prob: np.ndarray) -> None:
    if len(y_true) != len(y_prob):
        raise KnhanesDataValidationError("y_true and y_prob must have the same length")
    if not y_true.isin([0, 1]).all() or y_true.nunique() != 2:
        raise KnhanesDataValidationError("y_true must contain both 0 and 1 only")
    if np.isnan(y_prob).any() or (y_prob < 0).any() or (y_prob > 1).any():
        raise KnhanesDataValidationError("y_prob must be between 0 and 1")
