from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score


@dataclass
class ThresholdResult:
    threshold: float
    recall: float
    precision: float
    f1: float


class ThresholdOptimizer:
    def __init__(
        self,
        min_recall: float = 0.8,
        thresholds: np.ndarray | None = None,
    ) -> None:
        if not 0 <= min_recall <= 1:
            raise ValueError("min_recall must be between 0 and 1")

        self.min_recall = min_recall
        self.thresholds = thresholds if thresholds is not None else np.arange(0.05, 0.96, 0.01)

        if np.any((self.thresholds < 0) | (self.thresholds > 1)):
            raise ValueError("thresholds must be between 0 and 1")

    def _validate_y_true_and_y_prob(self, y_true: pd.Series | np.ndarray, y_prob: np.ndarray) -> None:
        if len(y_true) != len(y_prob):
            raise ValueError("y_true and y_prob must have the same length")

        if np.any((y_prob < 0) | (y_prob > 1)):
            raise ValueError("y_prob must contain values between 0 and 1")

    def optimize(
        self,
        y_true: pd.Series | np.ndarray,
        y_prob: np.ndarray,
    ) -> ThresholdResult:
        self._validate_y_true_and_y_prob(y_true, y_prob)

        results: list[ThresholdResult] = []

        for threshold in self.thresholds:
            y_pred = (y_prob >= threshold).astype(int)

            # 재현율 계산
            recall = recall_score(y_true, y_pred, zero_division=0)
            # 정밀도 계산
            precision = precision_score(y_true, y_pred, zero_division=0)
            # f1 Score 계산
            f1 = f1_score(y_true, y_pred, zero_division=0)

            # 실험결과 도출
            results.append(
                ThresholdResult(
                    threshold=threshold,
                    recall=recall,
                    precision=precision,
                    f1=f1,
                )
            )

        # 실험 결과에서 최소 Recall 조건을 만족하는 threshold만 선택
        candidates = [result for result in results if result.recall >= self.min_recall]

        # 최소 재현율을 만족하는 threshold가 없을 경우 에러 발생
        if not candidates:
            raise ValueError(f"No threshold satisfies minimum recall of {self.min_recall:.2f}")

        # 1순위 - f1 Score가 가장 높은 threshold 선택
        # 2순위 - 재현율이 가장 높은 threshold 선택
        # 3순위 - 정밀도가 가장 높은 threshold 선택
        return max(
            candidates,
            key=lambda result: (
                result.f1,
                result.recall,
                result.precision,
            ),
        )
