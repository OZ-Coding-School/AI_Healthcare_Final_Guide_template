from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass
class EvaluationMetrics:
    model: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    specificity: float
    auc: float | None = None


@dataclass
class EvaluationResult:
    metrics: EvaluationMetrics
    confusion_matrix: np.ndarray
    classification_report: dict[str, Any]
    y_true: pd.Series
    y_pred: np.ndarray
    y_prob: np.ndarray | None = None


class ModelEvaluator:
    def __init__(
        self,
        model: Any,
        preprocessor: ColumnTransformer,
        x_test: pd.DataFrame,
        y_test: pd.Series,
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor
        self.x_test = x_test
        self.y_test = y_test

    def evaluate(self) -> EvaluationResult:
        """
        테스트 데이터를 기반으로 모델의 성능 평가를 수행하고, 평가 결과와 관련된 각종 메트릭 및 리포트를 반환합니다.
        """
        # 테스트 데이터 전처리 수행
        x_test_proc = self.preprocessor.transform(self.x_test)

        # 테스트 데이터로 예측 수행
        y_pred = self.model.predict(x_test_proc)

        # 각 지표계산

        # 정확도 (TP + TN / (TP + TN + FP + FN))
        accuracy = accuracy_score(self.y_test, y_pred)
        # 정밀도 (TP / (TP + FN))
        precision = precision_score(self.y_test, y_pred, zero_division=0)
        # 재현율 (TP / (TP + FP))
        recall = recall_score(self.y_test, y_pred, zero_division=0)
        # F1 score (2 * (precision * recall) / (precision + recall))
        f1 = f1_score(self.y_test, y_pred, zero_division=0)

        # 예측 결과 confusion matrix 도출
        cm = confusion_matrix(self.y_test, y_pred)

        # 민감도 (tp / (tp + fn))
        tn, fp, fn, tp = cm.ravel()
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        metrics = EvaluationMetrics(
            model=self.model.__class__.__name__,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            specificity=specificity,
        )
        # 만약 proba(모델의 양성 확률 예측값)가 존재하는 모델이면 auc 계산하여 추가
        y_prob = None
        if hasattr(self.model, "predict_proba"):
            y_prob = self.model.predict_proba(x_test_proc)[:, 1]
            metrics.auc = roc_auc_score(self.y_test, y_prob)

        # 예측 결과 classification report 도출
        report = classification_report(
            self.y_test,
            y_pred,
            output_dict=True,
            zero_division=0,
        )
        assert isinstance(report, dict)

        return EvaluationResult(
            metrics=metrics,
            confusion_matrix=cm,
            classification_report=report,
            y_true=self.y_test,
            y_pred=y_pred,
            y_prob=y_prob,
        )
