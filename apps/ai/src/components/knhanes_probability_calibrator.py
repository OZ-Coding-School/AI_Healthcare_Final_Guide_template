"""
모델의 양성 확률을 실제 양성 비율에 맞게 보정합니다.

보정기는 Train의 OOF 확률로 학습하고, 방법 선택도 OOF 안에서 폴드를 나눠 평가합니다.
Validation은 보정 효과 확인에만 씁니다.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.knhanes_tuning_configs import (
    CALIBRATION_ECE_BINS,
    CALIBRATION_METHODS,
    CALIBRATION_PROBABILITY_EPSILON,
)


@dataclass(frozen=True)
class CalibrationMetrics:
    rows: int
    positive_rate: float
    mean_predicted: float
    brier: float
    log_loss: float
    ece: float


@dataclass(frozen=True)
class CalibrationComparison:
    method: str
    cv_log_loss: float
    cv_brier: float


class ProbabilityCalibrator:
    """
    none: 보정하지 않음
    sigmoid: 원 확률의 logit에 로지스틱 회귀를 적합(Platt scaling)
    isotonic: 단조 증가 계단 함수 적합
    """

    def __init__(self, method: str, epsilon: float = CALIBRATION_PROBABILITY_EPSILON) -> None:
        if method not in CALIBRATION_METHODS:
            raise ValueError(f"Unknown calibration method: {method}")
        if not 0 < epsilon < 0.5:
            raise ValueError("epsilon must be between 0 and 0.5")
        self.method = method
        self.epsilon = epsilon
        self._estimator: LogisticRegression | IsotonicRegression | None = None
        self.is_fitted = False

    def fit(self, raw_prob: np.ndarray, y_true: pd.Series | np.ndarray) -> "ProbabilityCalibrator":
        raw_prob, labels = _validate(raw_prob, y_true)
        if self.method == "sigmoid":
            self._estimator = LogisticRegression(C=1e6, max_iter=1000)
            self._estimator.fit(self._logit(raw_prob).reshape(-1, 1), labels)
        elif self.method == "isotonic":
            self._estimator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            self._estimator.fit(raw_prob, labels)
        self.is_fitted = True
        return self

    def transform(self, raw_prob: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("ProbabilityCalibrator must be fitted before transform")
        raw_prob = _validate_probabilities(raw_prob)
        if isinstance(self._estimator, LogisticRegression):
            calibrated = self._estimator.predict_proba(self._logit(raw_prob).reshape(-1, 1))[:, 1]
        elif isinstance(self._estimator, IsotonicRegression):
            calibrated = self._estimator.predict(raw_prob)
        else:
            calibrated = raw_prob
        return np.clip(np.asarray(calibrated, dtype=float), self.epsilon, 1 - self.epsilon)

    def _logit(self, prob: np.ndarray) -> np.ndarray:
        clipped = np.clip(prob, self.epsilon, 1 - self.epsilon)
        return np.log(clipped / (1 - clipped))


def select_calibrator(
    oof_prob: np.ndarray,
    y_true: pd.Series,
    folds: list[tuple[np.ndarray, np.ndarray]],
    methods: list[str] = CALIBRATION_METHODS,
) -> tuple[ProbabilityCalibrator, list[CalibrationComparison]]:
    """
    OOF 확률 안에서 폴드를 다시 나눠 방법별 보정 성능을 비교합니다.
    같은 OOF로 학습하고 평가하면 Isotonic이 과대평가되므로, 평가 폴드는 보정기 학습에서 뺍니다.
    Log loss가 가장 낮은 방법을 OOF 전체로 다시 학습해 반환합니다.
    """
    oof_prob, labels = _validate(oof_prob, y_true)
    if not methods:
        raise ValueError("methods must not be empty")

    comparisons = []
    for method in methods:
        calibrated = np.full(len(labels), np.nan)
        for train_idx, validation_idx in folds:
            if len(np.unique(labels[train_idx])) != 2:
                raise KnhanesDataValidationError("Every calibration fold must contain both classes")
            calibrator = ProbabilityCalibrator(method).fit(oof_prob[train_idx], labels[train_idx])
            calibrated[validation_idx] = calibrator.transform(oof_prob[validation_idx])
        if np.isnan(calibrated).any():
            raise KnhanesDataValidationError("Folds must cover every OOF row exactly once")
        comparisons.append(
            CalibrationComparison(
                method=method,
                cv_log_loss=float(log_loss(labels, calibrated, labels=[0, 1])),
                cv_brier=float(brier_score_loss(labels, calibrated)),
            )
        )

    best = min(comparisons, key=lambda comparison: (comparison.cv_log_loss, methods.index(comparison.method)))
    return ProbabilityCalibrator(best.method).fit(oof_prob, labels), comparisons


def compute_calibration_metrics(
    y_true: pd.Series | np.ndarray, prob: np.ndarray, n_bins: int = CALIBRATION_ECE_BINS
) -> CalibrationMetrics:
    prob, labels = _validate(prob, y_true)
    return CalibrationMetrics(
        rows=len(labels),
        positive_rate=float(labels.mean()),
        mean_predicted=float(prob.mean()),
        brier=float(brier_score_loss(labels, prob)),
        log_loss=float(log_loss(labels, prob, labels=[0, 1])),
        ece=expected_calibration_error(labels, prob, n_bins),
    )


def expected_calibration_error(labels: np.ndarray, prob: np.ndarray, n_bins: int = CALIBRATION_ECE_BINS) -> float:
    """확률을 같은 폭 구간으로 나눠 구간별 |평균 예측 - 실제 양성률|을 행 수로 가중 평균합니다."""
    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")
    bin_ids = np.minimum((prob * n_bins).astype(int), n_bins - 1)
    error = 0.0
    for bin_id in np.unique(bin_ids):
        mask = bin_ids == bin_id
        error += mask.mean() * abs(prob[mask].mean() - labels[mask].mean())
    return float(error)


def _validate(prob: np.ndarray, y_true: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    prob = _validate_probabilities(prob)
    labels = np.asarray(y_true)
    if len(prob) != len(labels):
        raise KnhanesDataValidationError("prob and y_true must have the same length")
    if not np.isin(labels, [0, 1]).all() or len(np.unique(labels)) != 2:
        raise KnhanesDataValidationError("y_true must contain both 0 and 1 only")
    return prob, labels.astype(int)


def _validate_probabilities(prob: np.ndarray) -> np.ndarray:
    prob = np.asarray(prob, dtype=float)
    if prob.ndim != 1:
        raise KnhanesDataValidationError("prob must be one-dimensional")
    if np.isnan(prob).any() or (prob < 0).any() or (prob > 1).any():
        raise KnhanesDataValidationError("prob must be between 0 and 1")
    return prob
