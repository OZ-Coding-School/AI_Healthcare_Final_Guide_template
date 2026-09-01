import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

logger = logging.getLogger(__name__)

StrategyType = Literal["f1", "recall", "precision", "youden_j"]


@dataclass
class ThresholdResult:
    threshold: float
    recall: float
    precision: float
    f1: float
    specificity: float = 0.0


class ThresholdOptimizer:
    def __init__(
        self,
        min_recall: float = 0.8,
        thresholds: np.ndarray | None = None,
        strategy: StrategyType = "f1",
        strict: bool = True,
    ) -> None:
        if not 0 <= min_recall <= 1:
            raise ValueError("min_recall must be between 0 and 1")

        valid_strategies = ("f1", "recall", "precision", "youden_j")
        if strategy not in valid_strategies:
            raise ValueError(f"Invalid strategy: '{strategy}'. Must be one of {valid_strategies}")

        self.min_recall = min_recall
        self.thresholds = thresholds if thresholds is not None else np.arange(0.01, 0.99, 0.01)
        self.strategy = strategy
        self.strict = strict

        if np.any((self.thresholds < 0) | (self.thresholds > 1)):
            raise ValueError("thresholds must be between 0 and 1")

    def _validate_y_true_and_y_prob(self, y_true: pd.Series | np.ndarray, y_prob: np.ndarray) -> None:
        if len(y_true) != len(y_prob):
            raise ValueError("y_true and y_prob must have the same length")

        if np.any((y_prob < 0) | (y_prob > 1)):
            raise ValueError("y_prob must contain values between 0 and 1")

    def _get_sort_key(self, result: ThresholdResult) -> tuple[float, ...]:
        match self.strategy:
            case "f1":
                return (result.f1, result.recall, result.precision)
            case "recall":
                return (result.recall, result.f1, result.precision)
            case "precision":
                return (result.precision, result.f1, result.recall)
            case "youden_j":
                youden_j = result.recall + result.specificity - 1.0
                return (youden_j, result.f1, result.recall)
            case _:
                return (result.f1, result.recall, result.precision)

    def optimize(
        self,
        y_true: pd.Series | np.ndarray,
        y_prob: np.ndarray,
    ) -> ThresholdResult:
        self._validate_y_true_and_y_prob(y_true, y_prob)
        y_true_arr = np.asarray(y_true)

        results: list[ThresholdResult] = []

        for threshold in self.thresholds:
            y_pred = (y_prob >= threshold).astype(int)

            recall = float(recall_score(y_true_arr, y_pred, zero_division=0))
            precision = float(precision_score(y_true_arr, y_pred, zero_division=0))
            f1 = float(f1_score(y_true_arr, y_pred, zero_division=0))

            tn = int(np.sum((y_true_arr == 0) & (y_pred == 0)))
            fp = int(np.sum((y_true_arr == 0) & (y_pred == 1)))
            specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

            results.append(
                ThresholdResult(
                    threshold=float(threshold),
                    recall=recall,
                    precision=precision,
                    f1=f1,
                    specificity=specificity,
                )
            )

        candidates = [result for result in results if result.recall >= self.min_recall]

        if not candidates:
            if self.strict:
                raise ValueError(f"No threshold satisfies minimum recall of {self.min_recall:.2f}")
            logger.warning(
                "No threshold satisfies minimum recall of %.2f. Falling back to optimal threshold across all candidates.",
                self.min_recall,
            )
            candidates = results

        return max(candidates, key=self._get_sort_key)
