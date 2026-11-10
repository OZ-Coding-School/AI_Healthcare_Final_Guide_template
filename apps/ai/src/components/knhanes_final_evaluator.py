from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.components.knhanes_multi_year_loader import KnhanesDataValidationError


@dataclass(frozen=True)
class MetricInterval:
    metric: str
    value: float
    ci_lower: float
    ci_upper: float


def bootstrap_metric_intervals(
    y_true: pd.Series | np.ndarray,
    prob: np.ndarray,
    households: pd.Series,
    iterations: int,
    confidence_level: float,
    random_state: int,
) -> list[MetricInterval]:
    """한 모델의 ROC-AUC, PR-AUC, Brier 신뢰구간을 가구 단위 부트스트랩으로 추정합니다."""
    labels = np.asarray(y_true)
    prob = np.asarray(prob, dtype=float)
    if not len(labels) == len(prob) == len(households):
        raise KnhanesDataValidationError("y_true, prob and households must have the same length")
    if not np.isin(labels, [0, 1]).all() or len(np.unique(labels)) != 2:
        raise KnhanesDataValidationError("y_true must contain both 0 and 1 only")
    if np.isnan(prob).any() or (prob < 0).any() or (prob > 1).any():
        raise KnhanesDataValidationError("prob must be between 0 and 1")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    metrics = {
        "roc_auc": roc_auc_score,
        "pr_auc": average_precision_score,
        "brier": brier_score_loss,
    }
    household_codes = pd.factorize(households)[0]
    household_count = int(household_codes.max()) + 1
    generator = np.random.default_rng(random_state)

    samples: dict[str, list[float]] = {name: [] for name in metrics}
    for _ in range(iterations):
        sampled = generator.integers(0, household_count, household_count)
        row_weights = np.bincount(sampled, minlength=household_count)[household_codes]
        if labels[row_weights > 0].min() == labels[row_weights > 0].max():
            continue
        for name, function in metrics.items():
            samples[name].append(float(function(labels, prob, sample_weight=row_weights)))

    if not samples["roc_auc"]:
        raise KnhanesDataValidationError("Bootstrap samples never contained both classes")

    tail = (1 - confidence_level) / 2 * 100
    intervals = []
    for name, function in metrics.items():
        ci_lower, ci_upper = np.percentile(samples[name], [tail, 100 - tail])
        intervals.append(MetricInterval(name, float(function(labels, prob)), float(ci_lower), float(ci_upper)))
    return intervals


def aggregate_shap_by_original_feature(
    shap_values: np.ndarray, feature_names: list[str], feature_metadata: list[Any] | None
) -> pd.DataFrame:
    """
    원-핫으로 나뉜 열의 SHAP 값을 행마다 원 변수 단위로 더한 뒤 |SHAP| 평균을 냅니다.
    열마다 따로 평균을 내고 더하면 같은 사람 안에서 서로 상쇄되는 기여가 과대평가됩니다.
    """
    shap_values = np.asarray(shap_values, dtype=float)
    if shap_values.ndim != 2 or shap_values.shape[1] != len(feature_names):
        raise KnhanesDataValidationError("shap_values columns must match feature_names")

    original_map = {name: name for name in feature_names}
    for item in feature_metadata or []:
        model_name = item["model_feature_name"] if isinstance(item, dict) else item.model_feature_name
        original = item["original_feature_name"] if isinstance(item, dict) else item.original_feature_name
        original_map[model_name] = original

    originals = [original_map[name] for name in feature_names]
    grouped = pd.DataFrame(shap_values, columns=feature_names).T.groupby(originals, sort=False).sum().T
    mean_abs = grouped.abs().mean(axis=0)
    mean_signed = grouped.mean(axis=0)
    total = float(mean_abs.sum())

    result = pd.DataFrame(
        {
            "feature": mean_abs.index,
            "importance": mean_abs.to_numpy(),
            "importance_ratio": mean_abs.to_numpy() / total if total > 0 else 0.0,
            "mean_shap": mean_signed.to_numpy(),
        }
    )
    return result.sort_values("importance", ascending=False).reset_index(drop=True)
