import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    auc as calculate_auc,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from src.components.model_trainer import ModelBundle

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    model: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    specificity: float
    threshold: float = 0.5
    auc: float | None = None
    pr_auc: float | None = None


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
        preprocessor: ColumnTransformer | None,
        x_test: pd.DataFrame,
        y_test: pd.Series,
        output_dir: Path | str,
        threshold: float = 0.5,
        feature_names: list[str] | None = None,
        post_preprocessor: ColumnTransformer | None = None,
        bundle: ModelBundle | None = None,
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor
        self.post_preprocessor = post_preprocessor
        self.x_test = x_test
        self.y_test = y_test
        self.output_dir = Path(output_dir)
        self.threshold = threshold
        self.feature_names = feature_names
        self.bundle = bundle
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_bundle(
        cls,
        bundle: ModelBundle,
        x_test: pd.DataFrame,
        y_test: pd.Series,
        output_dir: Path | str,
        threshold: float | None = None,
    ) -> "ModelEvaluator":
        return cls(
            model=bundle.model,
            preprocessor=bundle.preprocessor,
            post_preprocessor=bundle.post_preprocessor,
            x_test=x_test,
            y_test=y_test,
            output_dir=output_dir,
            threshold=threshold if threshold is not None else bundle.threshold,
            feature_names=bundle.feature_names,
            bundle=bundle,
        )

    def run(self) -> None:
        result = self.evaluate()
        self.save(result)

    def _transform_test_data(self) -> np.ndarray:
        if self.bundle is not None:
            return self.bundle.transform(self.x_test)

        x_proc = self.preprocessor.transform(self.x_test) if self.preprocessor is not None else self.x_test

        if self.post_preprocessor is not None:
            x_proc = self.post_preprocessor.transform(x_proc)

        if hasattr(x_proc, "toarray"):
            x_proc = x_proc.toarray()
        elif hasattr(x_proc, "to_numpy"):
            x_proc = x_proc.to_numpy()
        return np.asarray(x_proc)

    def evaluate(self) -> EvaluationResult:
        """
        테스트 데이터를 기반으로 모델의 성능 평가를 수행하고, 평가 결과와 관련된 각종 메트릭 및 리포트를 반환합니다.
        """
        x_test_proc = self._transform_test_data()

        y_prob = None
        if hasattr(self.model, "predict_proba"):
            classes = np.asarray(self.model.classes_)
            positive_class_indices = np.flatnonzero(classes == 1)
            if positive_class_indices.size != 1:
                raise ValueError("Model must contain exactly one positive class labeled 1")
            y_prob = self.model.predict_proba(x_test_proc)[:, positive_class_indices[0]]
            if self.bundle is not None:
                y_prob = self.bundle.calibrate(y_prob)
        elif hasattr(self.model, "decision_function"):
            y_prob = self.model.decision_function(x_test_proc)

        if y_prob is not None:
            y_pred = (y_prob >= self.threshold).astype(int)
        else:
            y_pred = self.model.predict(x_test_proc)

        # 각 지표 계산
        accuracy = accuracy_score(self.y_test, y_pred)
        precision = precision_score(self.y_test, y_pred, zero_division=0)
        recall = recall_score(self.y_test, y_pred, zero_division=0)
        f1 = f1_score(self.y_test, y_pred, zero_division=0)

        # 예측 결과 confusion matrix 도출
        cm = confusion_matrix(self.y_test, y_pred)
        if cm.size == 4:
            tn, fp, fn, tp = cm.ravel()
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        else:
            specificity = 0.0

        auc: float | None = None
        pr_auc: float | None = None
        if y_prob is not None:
            try:
                auc = float(roc_auc_score(self.y_test, y_prob))
            except ValueError:
                auc = None

            try:
                precision_curve, recall_curve, _ = precision_recall_curve(self.y_test, y_prob)
                pr_auc = float(calculate_auc(recall_curve, precision_curve))
            except ValueError:
                pr_auc = None

        metrics = EvaluationMetrics(
            model=self.model.__class__.__name__,
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1=float(f1),
            specificity=float(specificity),
            threshold=float(self.threshold),
            auc=auc,
            pr_auc=pr_auc,
        )

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

    def save(self, result: EvaluationResult) -> None:
        """
        주어진 결과 데이터를 파일에 저장하고 차트 및 XAI 리포트를 생성합니다.
        """
        # 모델 평가 매트릭 csv 파일 저장
        self._save_metrics_to_csv(result.metrics)
        # 분류 보고서 csv 파일 저장
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

        # 피처 중요도(Feature Importance) 추출 및 저장
        self._save_feature_importance()

    def _get_feature_names(self, expected_len: int) -> list[str]:
        if self.feature_names and len(self.feature_names) == expected_len:
            return list(self.feature_names)

        if self.post_preprocessor is not None and hasattr(self.post_preprocessor, "get_feature_names_out"):
            try:
                names = self.post_preprocessor.get_feature_names_out().tolist()
                if len(names) == expected_len:
                    return names
            except Exception:
                pass

        if self.preprocessor is not None and hasattr(self.preprocessor, "get_feature_names_out"):
            try:
                names = self.preprocessor.get_feature_names_out().tolist()
                if len(names) == expected_len:
                    return names
            except Exception:
                pass

        if isinstance(self.x_test, pd.DataFrame) and len(self.x_test.columns) == expected_len:
            return list(self.x_test.columns)

        return [f"feature_{i}" for i in range(expected_len)]

    def _save_feature_importance(self) -> None:
        """
        모델의 피처 중요도(feature_importances_ 또는 coef_)를 추출하여 CSV 및 시각화 이미지로 저장합니다.
        """
        importances: np.ndarray | None = None
        if hasattr(self.model, "feature_importances_"):
            importances = np.array(self.model.feature_importances_)
        elif hasattr(self.model, "coef_"):
            importances = np.abs(np.array(self.model.coef_)).flatten()

        if importances is None or len(importances) == 0:
            return

        feature_names = self._get_feature_names(len(importances))
        df_imp = (
            pd.DataFrame(
                {
                    "feature": feature_names,
                    "importance": importances,
                }
            )
            .sort_values(by="importance", ascending=False)
            .reset_index(drop=True)
        )

        df_imp.to_csv(self.output_dir / "feature_importance.csv", index=False)

        top_df = df_imp.head(20)
        plt.figure(figsize=(10, max(5.0, len(top_df) * 0.35)))
        sns.barplot(
            data=top_df,
            x="importance",
            y="feature",
            hue="feature",
            legend=False,
            palette="viridis",
        )
        plt.title(f"Feature Importance ({self.model.__class__.__name__})")
        plt.xlabel("Importance")
        plt.ylabel("Feature")
        self._save_plot(filename="feature_importance.png")

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

        self._save_plot(filename="confusion_matrix.png")

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

        self._save_plot(filename="roc_curve.png")

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
        self._save_plot(filename="precision_recall_curve.png")

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

        self._save_plot(filename="probability_distribution.png")

    def _save_plot(self, filename: str) -> None:
        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=300)
        plt.close()

    def _save_classification_report_to_csv(self, report: dict[str, Any]) -> None:
        """
        주어진 분류 보고서를 CSV 파일로 저장합니다.
        """
        pd.DataFrame(report).T.to_csv(self.output_dir / "classification_report.csv")

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
            self.output_dir / "predictions.csv",
            index=False,
        )

    def _save_metrics_to_csv(self, metrics: EvaluationMetrics) -> None:
        """
        평가 결과에 대한 메트릭을 CSV 파일로 저장합니다.
        """
        pd.DataFrame([asdict(metrics)]).to_csv(
            self.output_dir / "metrics.csv",
            index=False,
        )
