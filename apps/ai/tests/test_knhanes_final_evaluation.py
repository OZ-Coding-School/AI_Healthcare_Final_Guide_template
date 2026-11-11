import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.components.knhanes_final_evaluator import aggregate_shap_by_original_feature, bootstrap_metric_intervals
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.components.knhanes_probability_calibrator import ProbabilityCalibrator
from src.components.knhanes_risk_threshold import (
    RiskThresholds,
    ThresholdConfusion,
    confusion_from_threshold_performance,
    threshold_confusions,
)
from src.components.model_trainer import BinaryClassificationModelTrainer, ModelBundle
from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType
from src.pipelines.knhanes_final_evaluation_pipeline import (
    FINAL_EVALUATION_SUPPLEMENT_NAME,
    FinalEvaluationAlreadyRunError,
    load_final_bundle,
    load_test_split,
    run_final_report_supplement,
    run_knhanes_final_evaluation,
    threshold_confusion_rows,
)

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK
TRAIN_SET = KnhanesTrainSet.TRAIN_B
TRAIN_ROWS, TEST_ROWS = 240, 160


def make_inputs(rows: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    generator = np.random.default_rng(seed)
    signal = generator.normal(size=rows)
    X = pd.DataFrame(
        {
            "나이": 50 + 10 * signal + generator.normal(size=rows),
            "총콜레스테롤": generator.normal(100, 10, rows),
        }
    )
    X["성별"] = pd.Categorical(generator.choice(["M", "F"], rows))
    y = pd.Series((signal + generator.normal(scale=0.7, size=rows) > 0.5).astype(int), name="disease_label")
    return X, y


def make_meta(rows: int, prefix: str, year: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [f"{prefix}{index}" for index in range(rows)],
            "ID_fam": [f"{prefix}F{index // 2}" for index in range(rows)],
            "year": year,
            "wt_itvex": 1.0,
        }
    )


@pytest.fixture
def evaluation_dirs(tmp_path: Path) -> dict[str, Path]:
    split_dir = tmp_path / "split"
    labeled_dir = tmp_path / "labeled"
    model_dir = tmp_path / "models"
    labeled_dir.mkdir()

    X_train, y_train = make_inputs(TRAIN_ROWS, seed=1)
    X_test, y_test = make_inputs(TEST_ROWS, seed=2)
    meta_test = make_meta(TEST_ROWS, "S", 2024.0)

    models = {}
    for model_type in ModelType:
        output_dir = split_dir / model_type / TRAIN_SET
        output_dir.mkdir(parents=True)
        X_train.to_parquet(output_dir / "X_train.parquet", index=False)
        make_meta(TRAIN_ROWS, "T", 2023.0).to_parquet(output_dir / "meta_train.parquet", index=False)
        X_test.to_parquet(output_dir / "X_test.parquet", index=False)
        y_test.to_frame().to_parquet(output_dir / "y_test.parquet", index=False)
        meta_test.to_parquet(output_dir / "meta_test.parquet", index=False)

        bundle = BinaryClassificationModelTrainer(
            X_train,
            y_train,
            algorithm=ModelAlgorithm.LIGHTGBM,
            hyperparameters={"n_estimators": 20, "verbose": -1, "n_jobs": 1},
        ).train()
        bundle.calibrator = ProbabilityCalibrator("sigmoid").fit(bundle.predict_proba(X_train), y_train)
        bundle.risk_thresholds = {"moderate": 0.2, "high": 0.6}
        model_path = model_dir / f"{model_type}.pkl"
        bundle.save(model_path)

        models[str(model_type)] = {
            "train_set": str(TRAIN_SET),
            "selected": {"algorithm": str(ModelAlgorithm.LIGHTGBM)},
            "saved_model_path": str(model_path),
            "validation_metrics": [
                {
                    "group": "all",
                    "model": "tuned_calibrated",
                    "positive_rate": 0.3,
                    "mean_predicted": 0.3,
                    "roc_auc": 0.8,
                    "pr_auc": 0.6,
                    "brier": 0.15,
                    "log_loss": 0.45,
                    "ece": 0.02,
                }
            ],
            "risk_threshold_performance": {},
        }

    tuning_report_path = tmp_path / "tuning_report.json"
    tuning_report_path.write_text(json.dumps({"test_split_used": False, "models": models}), encoding="utf-8")

    diagnosed = np.arange(TEST_ROWS) % 10 == 0
    pd.DataFrame(
        {"ID": meta_test["ID"], "DE1_dg": np.where(diagnosed, 1.0, 0.0), "DE1_31": 0.0, "DE1_32": 0.0}
    ).to_parquet(labeled_dir / f"{D}.parquet", index=False)
    pd.DataFrame({"ID": meta_test["ID"], "DI1_pr": np.where(diagnosed, 1.0, 0.0), "DI1_2": 5.0}).to_parquet(
        labeled_dir / f"{H}.parquet", index=False
    )
    return {
        "split": split_dir,
        "labeled": labeled_dir,
        "models": model_dir,
        "tuning_report": tuning_report_path,
        "report": tmp_path / "final",
    }


def run(dirs: dict[str, Path]) -> dict:
    return run_knhanes_final_evaluation(
        split_data_dir=dirs["split"],
        labeled_data_dir=dirs["labeled"],
        tuning_report_path=dirs["tuning_report"],
        report_dir=dirs["report"],
        bootstrap_iterations=20,
        shap_max_samples=50,
    )


# --- 신뢰구간, SHAP 집계 ---


def test_metric_intervals_contain_point_estimate():
    generator = np.random.default_rng(1)
    labels = generator.integers(0, 2, 400)
    prob = np.clip(labels * 0.4 + generator.uniform(0, 0.6, 400), 0, 1)

    intervals = bootstrap_metric_intervals(labels, prob, pd.Series(np.arange(400) // 2), 50, 0.95, 42)

    assert [interval.metric for interval in intervals] == ["roc_auc", "pr_auc", "brier"]
    assert all(interval.ci_lower <= interval.value <= interval.ci_upper for interval in intervals)


def test_metric_intervals_reject_invalid_input():
    with pytest.raises(KnhanesDataValidationError):
        bootstrap_metric_intervals(np.array([1, 1]), np.array([0.2, 0.3]), pd.Series([0, 1]), 10, 0.95, 42)
    with pytest.raises(KnhanesDataValidationError):
        bootstrap_metric_intervals(np.array([0, 1]), np.array([0.2]), pd.Series([0, 1]), 10, 0.95, 42)


def test_shap_aggregation_sums_one_hot_columns_per_row():
    shap_values = np.array([[0.5, -0.5, 0.2], [0.1, 0.3, -0.2]])
    names = ["성별_F", "성별_M", "나이"]
    metadata = [
        {"model_feature_name": "성별_F", "original_feature_name": "성별"},
        {"model_feature_name": "성별_M", "original_feature_name": "성별"},
        {"model_feature_name": "나이", "original_feature_name": "나이"},
    ]

    result = aggregate_shap_by_original_feature(shap_values, names, metadata).set_index("feature")

    # 첫 행은 성별 기여가 0으로 상쇄되고, 둘째 행은 0.4입니다.
    assert result.loc["성별", "importance"] == pytest.approx(0.2)
    assert result.loc["나이", "importance"] == pytest.approx(0.2)
    assert result["importance_ratio"].sum() == pytest.approx(1.0)


def test_shap_aggregation_rejects_mismatched_names():
    with pytest.raises(KnhanesDataValidationError):
        aggregate_shap_by_original_feature(np.zeros((2, 2)), ["a"], None)


# --- 최종 모델·Test 검증 ---


def test_final_bundle_requires_calibrator_and_thresholds(evaluation_dirs, tmp_path: Path):
    bundle = ModelBundle.load(evaluation_dirs["models"] / f"{D}.pkl")
    bundle.risk_thresholds = None
    bundle.save(tmp_path / "no_thresholds.pkl")
    bundle.calibrator = None
    bundle.save(tmp_path / "no_calibrator.pkl")

    with pytest.raises(KnhanesDataValidationError, match="risk thresholds"):
        load_final_bundle(tmp_path / "no_thresholds.pkl")
    with pytest.raises(KnhanesDataValidationError, match="calibrator"):
        load_final_bundle(tmp_path / "no_calibrator.pkl")


def test_test_split_must_be_2024(evaluation_dirs):
    path = evaluation_dirs["split"] / D / TRAIN_SET / "meta_test.parquet"
    meta = pd.read_parquet(path)
    meta.loc[0, "year"] = 2023.0
    meta.to_parquet(path, index=False)
    bundle = load_final_bundle(evaluation_dirs["models"] / f"{D}.pkl")

    with pytest.raises(KnhanesDataValidationError, match="only 2024"):
        load_test_split(evaluation_dirs["split"], D, TRAIN_SET, bundle)


def test_test_split_must_not_share_households_with_train(evaluation_dirs):
    path = evaluation_dirs["split"] / D / TRAIN_SET / "meta_test.parquet"
    meta = pd.read_parquet(path)
    meta.loc[0, "ID_fam"] = "TF0"
    meta.to_parquet(path, index=False)
    bundle = load_final_bundle(evaluation_dirs["models"] / f"{D}.pkl")

    with pytest.raises(KnhanesDataValidationError, match="households are in Train and Test"):
        load_test_split(evaluation_dirs["split"], D, TRAIN_SET, bundle)


def test_test_split_columns_must_match_training(evaluation_dirs):
    path = evaluation_dirs["split"] / D / TRAIN_SET / "X_test.parquet"
    pd.read_parquet(path).drop(columns=["나이"]).to_parquet(path, index=False)
    bundle = load_final_bundle(evaluation_dirs["models"] / f"{D}.pkl")

    with pytest.raises(KnhanesDataValidationError, match="columns differ"):
        load_test_split(evaluation_dirs["split"], D, TRAIN_SET, bundle)


def test_tuning_report_that_used_test_is_rejected(evaluation_dirs):
    report = json.loads(evaluation_dirs["tuning_report"].read_text(encoding="utf-8"))
    report["test_split_used"] = True
    evaluation_dirs["tuning_report"].write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(KnhanesDataValidationError, match="must not have used"):
        run(evaluation_dirs)


# --- 파이프라인 ---


def test_final_evaluation_saves_reports_and_shap(evaluation_dirs):
    report = run(evaluation_dirs)
    report_dir = evaluation_dirs["report"]

    assert report["test_split_used"] is True
    assert json.loads((report_dir / "final_evaluation_report.json").read_text(encoding="utf-8")) == report
    assert "2024년 Test" in (report_dir / "final_evaluation_report.md").read_text(encoding="utf-8")

    for model_type in ModelType:
        summary = report["models"][str(model_type)]
        assert set(summary["metrics"]) == {"all", "undiagnosed"}
        assert len(summary["model_sha256"]) == 64
        shares = summary["metrics"]["all"]["risk_level_shares"]
        assert sum(shares.values()) == pytest.approx(1.0)
        shap_dir = report_dir / model_type / "shap"
        importance = pd.read_csv(shap_dir / "shap_original_feature_importance.csv")
        assert set(importance["feature"]) == {"나이", "총콜레스테롤", "성별"}
        assert (report_dir / model_type / "metrics.csv").exists()


def test_final_evaluation_runs_only_once(evaluation_dirs):
    run(evaluation_dirs)

    with pytest.raises(FinalEvaluationAlreadyRunError):
        run(evaluation_dirs)


def test_threshold_confusion_counts_and_f1():
    labels = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    prob = np.array([0.9, 0.5, 0.1, 0.7, 0.4, 0.3, 0.1, 0.05])

    moderate, high = threshold_confusions(labels, prob, RiskThresholds(moderate=0.35, high=0.8))

    assert (moderate.true_positive, moderate.false_positive, moderate.true_negative, moderate.false_negative) == (
        2,
        2,
        3,
        1,
    )
    assert moderate.precision == pytest.approx(0.5)
    assert moderate.recall == pytest.approx(2 / 3)
    assert moderate.f1 == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))
    assert (high.true_positive, high.false_positive, high.true_negative, high.false_negative) == (1, 0, 5, 2)


def test_confusion_without_flagged_rows_has_zero_precision_and_f1():
    confusion = ThresholdConfusion.from_counts("HIGH", 0.9, 0, 0, 5, 3)
    assert confusion.precision == 0.0
    assert confusion.f1 == 0.0


def test_final_evaluation_saves_threshold_confusion(evaluation_dirs):
    report = run(evaluation_dirs)
    for summary in report["models"].values():
        for metrics in summary["metrics"].values():
            levels = [row["level"] for row in metrics["threshold_confusion"]]
            assert levels == ["MODERATE", "HIGH"]
    assert "혼동 행렬" in (evaluation_dirs["report"] / "final_evaluation_report.md").read_text(encoding="utf-8")


def test_confusion_restored_from_saved_performance_matches_direct_counts(evaluation_dirs):
    report = run(evaluation_dirs)
    for summary in report["models"].values():
        for metrics in summary["metrics"].values():
            restored = threshold_confusion_rows(
                {key: value for key, value in metrics.items() if key != "threshold_confusion"}
            )
            assert restored == metrics["threshold_confusion"]


def test_confusion_restoration_rejects_inconsistent_report():
    performance = {
        "level": "HIGH",
        "threshold": 0.5,
        "recall": 0.5,
        "specificity": 0.8,
        "precision": 0.9,
        "flagged_rate": 0.2,
    }
    with pytest.raises(KnhanesDataValidationError):
        confusion_from_threshold_performance(rows=100, positive_rate=0.2, performance=performance)


def test_supplement_keeps_test_record_and_adds_confusion(evaluation_dirs):
    run(evaluation_dirs)
    report_dir = evaluation_dirs["report"]
    report_path = report_dir / "final_evaluation_report.json"
    # 혼동 행렬이 없던 이전 보고서 형식으로 되돌립니다.
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = {
        model_type: {group: metrics.pop("threshold_confusion") for group, metrics in summary["metrics"].items()}
        for model_type, summary in report["models"].items()
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    original_record = report_path.read_bytes()

    supplement = run_final_report_supplement(report_dir)

    assert report_path.read_bytes() == original_record
    assert supplement["models"] == expected
    saved = json.loads((report_dir / FINAL_EVALUATION_SUPPLEMENT_NAME).read_text(encoding="utf-8"))
    assert saved["test_split_reused"] is False
    assert "혼동 행렬" in (report_dir / "final_evaluation_report.md").read_text(encoding="utf-8")
