from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from sklearn.metrics import precision_recall_curve, roc_curve

from core import settings
from core.utils.model_evaluator import EvaluationMetrics, EvaluationResult


class ModelEvaluationReporter:
    def __init__(
        self,
        *,
        output_basename: str,
        output_dir: Path = settings.MODEL_DIR / "reports",
    ) -> None:
        self.output_dir = output_dir
        self.output_basename = output_basename
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, result: EvaluationResult) -> None:
        """
        주어진 결과 데이터를 파일 또는 데이터베이스에 저장합니다.

        이 함수는 세 가지 주요 결과 데이터를 처리합니다:
        - 평가 메트릭스
        - 혼동 행렬(시각화 이미지)
        - 분류 보고서

        :param result: 저장할 결과 데이터를 포함하는 딕셔너리.
            - "metrics": 평가 메트릭스 데이터
            - "confusion_matrix": 혼동 행렬 데이터
            - "classification_report": 분류 보고서 데이터
        :type result: dict[str, Any]
        """
        # 모델 평가 매트릭 csv 파일저장
        self._save_metrics_to_csv(result.metrics)
        # 분류 보고서 csv 파일저장
        self._save_classification_report_to_csv(result.classification_report)
        # 혼동 행렬 시각화 이미지 저장
        self._save_confusion_matrix(result.confusion_matrix)

        # 만약 예측 확률이 제공된 경우
        if result.y_prob is not None:
            # 실제 값과 예측값 비교 데이터 csv 저장
            self._save_predictions_to_csv(result.y_true, result.y_pred, result.y_prob)
            # roc curve 시각화 이미지 저장
            self._save_roc_curve(result.y_true, result.y_prob)
            # precision recall curve 시각화 이미지 저장
            self._save_precision_recall_curve(result.y_true, result.y_prob)
            # 예측 확률 분포 시각화 이미지 저장
            self._save_prediction_distribution(result.y_true, result.y_prob)

    def _save_confusion_matrix(self, cm: np.ndarray) -> None:
        """
        혼동 행렬을 히트맵 이미지로 저장합니다.
        """
        plt.figure(figsize=(5, 4))

        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=["Negative", "Positive"],
            yticklabels=["Negative", "Positive"],
        )

        plt.xlabel("Predicted")
        plt.ylabel("Actual")
        plt.title("Confusion Matrix")

        self._save_plot(filename=f"{self.output_basename}_confusion_matrix.png")

    def _save_roc_curve(
        self,
        y_true: pd.Series,
        y_prob: np.ndarray,
    ) -> None:
        fpr, tpr, _ = roc_curve(y_true, y_prob)

        plt.figure(figsize=(6, 6))
        plt.plot(fpr, tpr, label="ROC")
        plt.plot([0, 1], [0, 1], "--")

        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("ROC Curve")
        plt.legend()

        self._save_plot(filename=f"{self.output_basename}_roc_curve.png")

    def _save_precision_recall_curve(
        self,
        y_true: pd.Series,
        y_prob: np.ndarray,
    ) -> None:
        precision, recall, _ = precision_recall_curve(
            y_true,
            y_prob,
        )

        plt.figure(figsize=(6, 6))
        plt.plot(recall, precision)

        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title("Precision-Recall Curve")

        plt.tight_layout()
        self._save_plot(filename=f"{self.output_basename}_precision_recall_curve.png")

    def _save_prediction_distribution(
        self,
        y_true: pd.Series,
        y_prob: np.ndarray,
    ) -> None:
        plt.figure(figsize=(6, 4))

        plt.hist(
            y_prob[y_true == 0],
            bins=30,
            alpha=0.6,
            label="Negative",
        )

        plt.hist(
            y_prob[y_true == 1],
            bins=30,
            alpha=0.6,
            label="Positive",
        )

        plt.xlabel("Predicted Probability")
        plt.ylabel("Count")
        plt.title("Prediction Probability Distribution")
        plt.legend()

        self._save_plot(filename=f"{self.output_basename}_probability_distribution.png")

    def _save_plot(self, filename: str) -> None:
        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=300)
        plt.close()

    def _save_classification_report_to_csv(self, report: dict[str, Any]) -> None:
        """
        주어진 분류 보고서를 CSV 파일로 저장합니다.
        """
        pd.DataFrame(report).T.to_csv(self.output_dir / f"{self.output_basename}_classification_report.csv")

    def _save_predictions_to_csv(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        y_prob: np.ndarray | None,
    ) -> None:
        df = pd.DataFrame(
            {
                "actual": y_true.to_numpy(),
                "predicted": y_pred,
            }
        )

        if y_prob is not None:
            df["probability"] = y_prob

        df.to_csv(
            self.output_dir / f"{self.output_basename}_predictions.csv",
            index=False,
        )

    def _save_metrics_to_csv(self, metrics: EvaluationMetrics) -> None:
        """
        평가 결과에 대한 메트릭을 CSV 파일로 저장합니다.
        """
        pd.DataFrame([asdict(metrics)]).to_csv(
            self.output_dir / f"{self.output_basename}_metrics.csv",
            index=False,
        )
