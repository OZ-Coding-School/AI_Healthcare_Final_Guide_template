"""
9번에서 확정한 최종 모델을 2024년 Test로 1회 평가하고 SHAP으로 설명합니다.

- 모델 선택, 보정, 임계값은 모두 9번에서 끝났습니다. 이 파이프라인은 아무것도 다시 고르지 않습니다.
- 같은 Test로 다시 평가하지 않도록, 결과 보고서가 이미 있으면 실행을 거부합니다.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.config import settings
from core.logger import configure_logger
from src.components.knhanes_baseline_evaluator import compute_baseline_metrics
from src.components.knhanes_final_evaluator import aggregate_shap_by_original_feature, bootstrap_metric_intervals
from src.components.knhanes_multi_year_loader import YEAR_VAR, KnhanesDataValidationError
from src.components.knhanes_probability_calibrator import compute_calibration_metrics
from src.components.knhanes_risk_threshold import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MODERATE,
    RiskThresholds,
    evaluate_thresholds,
)
from src.components.model_evaluator import ModelEvaluator
from src.components.model_trainer import ModelBundle
from src.components.shap_explainer import ShapExplainer
from src.enums import KnhanesTrainSet, ModelType
from src.knhanes_evaluation_configs import (
    FINAL_EVALUATION_BOOTSTRAP_ITERATIONS,
    FINAL_EVALUATION_CONFIDENCE_LEVEL,
    FINAL_EVALUATION_RANDOM_STATE,
    FINAL_TEST_YEAR,
    SHAP_MAX_SAMPLES,
    SHAP_TOP_FEATURES,
)
from src.pipelines.knhanes_data_pipeline import LABELED_DATA_DIR, SPLIT_DATA_DIR
from src.pipelines.knhanes_training_pipeline import HOUSEHOLD_VAR, ID_VAR, WEIGHT_VAR, load_diagnosed_flags
from src.pipelines.knhanes_tuning_pipeline import TUNING_REPORT_DIR

logger = configure_logger("KNHANES Final Evaluation")

FINAL_EVALUATION_REPORT_DIR = settings.MODEL_REPORT_DIR / "knhanes_final_evaluation"
FINAL_EVALUATION_REPORT_NAME = "final_evaluation_report.json"
LEVELS = [RISK_LEVEL_LOW, RISK_LEVEL_MODERATE, RISK_LEVEL_HIGH]


class FinalEvaluationAlreadyRunError(RuntimeError):
    """Test 평가 결과가 이미 있어 다시 평가하지 않습니다."""


def load_final_models(tuning_report_path: Path) -> dict[ModelType, dict[str, Any]]:
    """9번 보고서에서 질환별 최종 모델 경로와 학습 구성, Validation 결과를 읽습니다."""
    if not tuning_report_path.exists():
        raise FileNotFoundError(f"Tuning report not found: {tuning_report_path}")
    report = json.loads(tuning_report_path.read_text(encoding="utf-8"))
    if report.get("test_split_used") is not False:
        raise KnhanesDataValidationError("Tuning report must not have used the Test split")

    models = {}
    for model_type in ModelType:
        summary = report.get("models", {}).get(str(model_type))
        if summary is None:
            raise KnhanesDataValidationError(f"{model_type}: missing in tuning report")
        models[model_type] = summary
    return models


def load_final_bundle(model_path: Path) -> ModelBundle:
    bundle = ModelBundle.load(model_path)
    if bundle.calibrator is None:
        raise KnhanesDataValidationError(f"{model_path.name}: calibrator is missing")
    if not bundle.risk_thresholds or set(bundle.risk_thresholds) != {"moderate", "high"}:
        raise KnhanesDataValidationError(f"{model_path.name}: risk thresholds are missing")
    return bundle


def load_test_split(
    split_data_dir: Path, model_type: ModelType, train_set: KnhanesTrainSet, bundle: ModelBundle
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Test를 읽고 연도, 입력 컬럼, 학습 데이터와의 가구 중복을 확인합니다."""
    split_dir = split_data_dir / model_type / train_set
    frames = {}
    for name in ["X_test", "y_test", "meta_test", "meta_train"]:
        path = split_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"KNHANES split file not found: {path}")
        frames[name] = pd.read_parquet(path)

    X_test, meta_test = frames["X_test"], frames["meta_test"]
    y_test = frames["y_test"].iloc[:, 0]
    if not len(X_test) == len(y_test) == len(meta_test):
        raise KnhanesDataValidationError(f"{model_type}: Test rows are not aligned")
    if not meta_test[YEAR_VAR].astype(int).eq(FINAL_TEST_YEAR).all():
        raise KnhanesDataValidationError(f"{model_type}: Test must contain only {FINAL_TEST_YEAR}")

    expected_columns = list(getattr(bundle.preprocessor, "feature_names_in_", X_test.columns))
    if X_test.columns.tolist() != expected_columns:
        raise KnhanesDataValidationError(f"{model_type}: Test columns differ from the training columns")

    shared = set(meta_test[HOUSEHOLD_VAR]) & set(frames["meta_train"][HOUSEHOLD_VAR])
    if shared:
        raise KnhanesDataValidationError(f"{model_type}: {len(shared)} households are in Train and Test")
    return X_test, y_test, meta_test


def run_knhanes_final_evaluation(
    split_data_dir: Path = SPLIT_DATA_DIR,
    labeled_data_dir: Path = LABELED_DATA_DIR,
    tuning_report_path: Path = TUNING_REPORT_DIR / "tuning_report.json",
    report_dir: Path = FINAL_EVALUATION_REPORT_DIR,
    bootstrap_iterations: int = FINAL_EVALUATION_BOOTSTRAP_ITERATIONS,
    shap_max_samples: int = SHAP_MAX_SAMPLES,
) -> dict[str, Any]:
    """
    1. 이미 평가했는지 확인 (했다면 중단)
    2. 9번 최종 모델과 Test 로드·검증
    3. 전체·미진단자 성능과 신뢰구간, 위험 등급 성능 계산 (Validation 결과와 나란히)
    4. 평가 그래프와 SHAP 산출물 저장
    """
    report_path = report_dir / FINAL_EVALUATION_REPORT_NAME
    if report_path.exists():
        raise FinalEvaluationAlreadyRunError(
            f"Test split was already evaluated: {report_path}. Do not evaluate the same Test again."
        )

    final_models = load_final_models(tuning_report_path)
    report_dir.mkdir(parents=True, exist_ok=True)

    summaries = {}
    for model_type, tuning_summary in final_models.items():
        summaries[str(model_type)] = _evaluate_model(
            model_type,
            tuning_summary,
            split_data_dir,
            labeled_data_dir,
            report_dir / model_type,
            bootstrap_iterations,
            shap_max_samples,
        )

    report = {
        "evaluated_split": "test",
        "test_split_used": True,
        "test_year": FINAL_TEST_YEAR,
        "bootstrap_iterations": bootstrap_iterations,
        "models": summaries,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "final_evaluation_report.md").write_text(render_final_report(report), encoding="utf-8")
    logger.info("Saved final evaluation report to %s", report_dir)
    return report


def _evaluate_model(
    model_type: ModelType,
    tuning_summary: dict[str, Any],
    split_data_dir: Path,
    labeled_data_dir: Path,
    output_dir: Path,
    bootstrap_iterations: int,
    shap_max_samples: int,
) -> dict[str, Any]:
    model_path = Path(tuning_summary["saved_model_path"])
    train_set = KnhanesTrainSet(tuning_summary["train_set"])
    bundle = load_final_bundle(model_path)
    thresholds = RiskThresholds(**bundle.risk_thresholds)
    X_test, y_test, meta_test = load_test_split(split_data_dir, model_type, train_set, bundle)

    prob = bundle.predict_proba(X_test)
    diagnosed = load_diagnosed_flags(labeled_data_dir, model_type, meta_test[ID_VAR]).to_numpy()
    masks = {"all": np.ones(len(y_test), dtype=bool), "undiagnosed": ~diagnosed}

    metrics = {}
    for group, mask in masks.items():
        ranking = compute_baseline_metrics(y_test[mask], prob[mask], meta_test.loc[mask, WEIGHT_VAR])
        calibration = compute_calibration_metrics(y_test[mask], prob[mask])
        intervals = bootstrap_metric_intervals(
            y_test[mask],
            prob[mask],
            meta_test.loc[mask, HOUSEHOLD_VAR],
            bootstrap_iterations,
            FINAL_EVALUATION_CONFIDENCE_LEVEL,
            FINAL_EVALUATION_RANDOM_STATE,
        )
        levels = thresholds.classify(prob[mask])
        metrics[group] = {
            **asdict(ranking),
            "log_loss": calibration.log_loss,
            "ece": calibration.ece,
            "intervals": [asdict(interval) for interval in intervals],
            "threshold_performance": [
                asdict(performance) for performance in evaluate_thresholds(y_test[mask], prob[mask], thresholds)
            ],
            "risk_level_shares": {level: float(np.mean(levels == level)) for level in LEVELS},
            "risk_level_positive_rates": {
                level: float(y_test[mask][levels == level].mean()) if (levels == level).any() else None
                for level in LEVELS
            },
        }

    ModelEvaluator.from_bundle(bundle, X_test, y_test, output_dir, threshold=thresholds.moderate).run()

    shap_result = ShapExplainer.from_bundle(bundle, random_state=FINAL_EVALUATION_RANDOM_STATE).explain_dataset(
        X_test, output_dir=output_dir / "shap", max_samples=shap_max_samples
    )
    grouped_importance = aggregate_shap_by_original_feature(
        shap_result.shap_values, shap_result.feature_names, bundle.feature_metadata
    )
    grouped_importance.to_csv(output_dir / "shap" / "shap_original_feature_importance.csv", index=False)

    return {
        "train_set": str(train_set),
        "algorithm": tuning_summary["selected"]["algorithm"],
        "model_path": str(model_path),
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "risk_thresholds": thresholds.to_dict(),
        "test_rows": int(len(y_test)),
        "metrics": metrics,
        "validation_metrics": [
            row for row in tuning_summary.get("validation_metrics", []) if row.get("model") == "tuned_calibrated"
        ],
        "validation_threshold_performance": tuning_summary.get("risk_threshold_performance", {}),
        "shap": {
            "samples": int(min(shap_max_samples, len(X_test))),
            "output_space": f"{_shap_output_space(bundle, shap_result.output_space)} (보정 전 원 모델 출력)",
            "top_features": grouped_importance.head(SHAP_TOP_FEATURES).to_dict(orient="records"),
        },
    }


def _shap_output_space(bundle: ModelBundle, reported: str) -> str:
    """부스팅 모델의 TreeExplainer 기본 출력은 확률이 아니라 log-odds입니다."""
    if bundle.model.__class__.__name__ in {"LGBMClassifier", "XGBClassifier", "GradientBoostingClassifier"}:
        return "log_odds"
    return reported


def render_final_report(report: dict[str, Any]) -> str:
    lines = [
        "# KNHANES 최종 평가 보고서 (2024년 Test)",
        "",
        f"- **평가 데이터:** {report['test_year']}년 Test. 모델·보정·임계값은 9번에서 확정했고, 이 평가로 바꾸지 않습니다.",
        f"- **신뢰구간:** 가구 단위 부트스트랩 {report['bootstrap_iterations']}회, 95%",
        "- **Validation:** 9번 보고서의 보정 모델 결과를 비교용으로 함께 적었습니다.",
    ]
    for model_type, summary in report["models"].items():
        lines += [
            "",
            f"## {model_type}",
            "",
            f"- **모델:** {summary['algorithm']} ({summary['train_set']})",
            f"- **위험 등급 경계:** MODERATE {summary['risk_thresholds']['moderate']:.4f}, "
            f"HIGH {summary['risk_thresholds']['high']:.4f}",
            f"- **Test 행 수:** {summary['test_rows']}",
            "",
            "### 성능 (Test vs Validation)",
            "",
            "| 집단 | 데이터 | 양성률 | 평균 예측 | ROC-AUC | PR-AUC | Brier | Log loss | ECE |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        validation_rows = {row["group"]: row for row in summary["validation_metrics"]}
        for group, metrics in summary["metrics"].items():
            intervals = {interval["metric"]: interval for interval in metrics["intervals"]}
            roc, pr = intervals["roc_auc"], intervals["pr_auc"]
            lines.append(
                f"| {group} | Test | {metrics['positive_rate']:.3f} | {metrics['mean_predicted']:.3f} "
                f"| {roc['value']:.3f} ({roc['ci_lower']:.3f}~{roc['ci_upper']:.3f}) "
                f"| {pr['value']:.3f} ({pr['ci_lower']:.3f}~{pr['ci_upper']:.3f}) "
                f"| {metrics['brier']:.4f} | {metrics['log_loss']:.4f} | {metrics['ece']:.4f} |"
            )
            validation = validation_rows.get(group)
            if validation:
                lines.append(
                    f"| {group} | Validation | {validation['positive_rate']:.3f} "
                    f"| {validation['mean_predicted']:.3f} | {validation['roc_auc']:.3f} "
                    f"| {validation['pr_auc']:.3f} | {validation['brier']:.4f} | {validation['log_loss']:.4f} "
                    f"| {validation['ece']:.4f} |"
                )

        lines += [
            "",
            "### 위험 등급 성능 (Test vs Validation)",
            "",
            "| 집단 | 경계 | 데이터 | 재현율 | 특이도 | 정밀도 | 해당 비율 |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
        for group, metrics in summary["metrics"].items():
            validation_performance = {
                row["level"]: row for row in summary["validation_threshold_performance"].get(group, [])
            }
            for performance in metrics["threshold_performance"]:
                for name, row in [
                    ("Test", performance),
                    ("Validation", validation_performance.get(performance["level"])),
                ]:
                    if row is None:
                        continue
                    lines.append(
                        f"| {group} | {performance['level']} 이상 | {name} | {row['recall']:.3f} "
                        f"| {row['specificity']:.3f} | {row['precision']:.3f} | {row['flagged_rate']:.3f} |"
                    )

        lines += [
            "",
            "### 등급별 분포와 실제 양성률 (Test)",
            "",
            "| 집단 | 등급 | 비율 | 실제 양성률 |",
            "|---|---|---:|---:|",
        ]
        for group, metrics in summary["metrics"].items():
            for level in LEVELS:
                positive_rate = metrics["risk_level_positive_rates"][level]
                positive_text = f"{positive_rate:.3f}" if positive_rate is not None else "-"
                lines.append(f"| {group} | {level} | {metrics['risk_level_shares'][level]:.3f} | {positive_text} |")

        shap = summary["shap"]
        lines += [
            "",
            f"### SHAP 원 변수 중요도 (Test {shap['samples']}건, 단위: {shap['output_space']})",
            "",
            "| 순위 | 변수 | 평균 \\|SHAP\\| | 비중 | 평균 SHAP |",
            "|---:|---|---:|---:|---:|",
        ]
        for rank, row in enumerate(shap["top_features"], start=1):
            lines.append(
                f"| {rank} | {row['feature']} | {row['importance']:.4f} | {row['importance_ratio']:.3f} "
                f"| {row['mean_shap']:+.4f} |"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run_knhanes_final_evaluation()
