import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.components.knhanes_baseline_evaluator import (
    PairedDifference,
    compare_paired_predictions,
    compute_baseline_metrics,
)
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType
from src.knhanes_training_configs import BLOOD_INPUT_COLUMNS
from src.pipelines.knhanes_training_pipeline import (
    load_baseline_dataset,
    load_diagnosed_flags,
    recommend_train_set,
    run_knhanes_baseline,
)

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK

BLOOD_MISSING_ROWS = 3


def make_inputs(rows: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    generator = np.random.default_rng(seed)
    signal = generator.normal(size=rows)
    data = {"나이": 50 + 10 * signal + generator.normal(size=rows)}
    data.update({column: generator.normal(100, 10, rows) for column in BLOOD_INPUT_COLUMNS})
    X = pd.DataFrame(data)
    X["성별"] = pd.Categorical(generator.choice(["M", "F"], rows))
    y = pd.Series((signal + generator.normal(scale=0.5, size=rows) > 0.5).astype(int), name="disease_label")
    return X, y


def make_meta(rows: int, start_id: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [f"A{index}" for index in range(start_id, start_id + rows)],
            "ID_fam": [f"F{index // 2}" for index in range(start_id, start_id + rows)],
            "year": [2022.0, 2023.0] * (rows // 2),
            "wt_itvex": 1.0,
            "wt_tot": 1.0,
            "kstrata": 1,
            "psu": 1,
        }
    )


@pytest.fixture
def split_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Test 파일 없이 Train과 Validation만 저장해 파이프라인이 Test를 읽지 않음을 함께 검증합니다."""
    split_dir = tmp_path / "split"
    labeled_dir = tmp_path / "labeled"
    labeled_dir.mkdir()

    train_rows, validation_rows = 240, 120
    X_validation, y_validation = make_inputs(validation_rows, seed=2)
    meta_validation = make_meta(validation_rows, start_id=0)
    y_validation.iloc[:BLOOD_MISSING_ROWS] = 1
    X_validation.loc[: BLOOD_MISSING_ROWS - 1, BLOOD_INPUT_COLUMNS] = np.nan

    for model_type in ModelType:
        for train_set in KnhanesTrainSet:
            output_dir = split_dir / model_type / train_set
            output_dir.mkdir(parents=True)
            X_train, y_train = make_inputs(train_rows, seed=1)
            y_train.iloc[:BLOOD_MISSING_ROWS] = 1
            X_train.loc[: BLOOD_MISSING_ROWS - 1, BLOOD_INPUT_COLUMNS] = np.nan
            X_train.to_parquet(output_dir / "X_train.parquet", index=False)
            y_train.to_frame().to_parquet(output_dir / "y_train.parquet", index=False)
            X_validation.to_parquet(output_dir / "X_validation.parquet", index=False)
            y_validation.to_frame().to_parquet(output_dir / "y_validation.parquet", index=False)
            meta_validation.to_parquet(output_dir / "meta_validation.parquet", index=False)

    diagnosed = np.arange(validation_rows) % 10 == 0
    pd.DataFrame(
        {"ID": meta_validation["ID"], "DE1_dg": np.where(diagnosed, 1.0, 0.0), "DE1_31": 0.0, "DE1_32": 0.0}
    ).to_parquet(labeled_dir / f"{D}.parquet", index=False)
    pd.DataFrame({"ID": meta_validation["ID"], "DI1_pr": np.where(diagnosed, 1.0, 0.0), "DI1_2": 5.0}).to_parquet(
        labeled_dir / f"{H}.parquet", index=False
    )
    return split_dir, labeled_dir


def make_difference(difference: float, significant: bool) -> PairedDifference:
    lower, upper = (difference - 0.001, difference + 0.001) if significant else (-0.01, 0.01)
    return PairedDifference("pr_auc", 0.5 + difference, 0.5, difference, lower, upper)


def test_compute_metrics_on_perfect_ranking():
    y_true = pd.Series([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])

    metrics = compute_baseline_metrics(y_true, y_prob, pd.Series([1.0, 1.0, 1.0, 1.0]))

    assert metrics.rows == 4
    assert metrics.roc_auc == pytest.approx(1.0)
    assert metrics.pr_auc == pytest.approx(1.0)
    assert metrics.brier == pytest.approx((0.01 + 0.04 + 0.04 + 0.01) / 4)
    assert metrics.mean_predicted == pytest.approx(0.5)


def test_weighted_auc_uses_survey_weights():
    y_true = pd.Series([0, 0, 1])
    y_prob = np.array([0.1, 0.9, 0.5])

    equal = compute_baseline_metrics(y_true, y_prob, pd.Series([1.0, 1.0, 1.0]))
    weighted = compute_baseline_metrics(y_true, y_prob, pd.Series([3.0, 1.0, 1.0]))

    assert equal.weighted_roc_auc == pytest.approx(0.5)
    assert weighted.weighted_roc_auc == pytest.approx(0.75)


@pytest.mark.parametrize(
    "y_true, y_prob",
    [
        (pd.Series([1, 1]), np.array([0.2, 0.8])),
        (pd.Series([0, 2]), np.array([0.2, 0.8])),
        (pd.Series([0, 1]), np.array([0.2, 1.8])),
        (pd.Series([0, 1]), np.array([0.2, np.nan])),
        (pd.Series([0, 1]), np.array([0.2])),
    ],
)
def test_compute_metrics_rejects_invalid_input(y_true: pd.Series, y_prob: np.ndarray):
    with pytest.raises(KnhanesDataValidationError):
        compute_baseline_metrics(y_true, y_prob, pd.Series([1.0] * len(y_true)))


def test_identical_predictions_have_no_difference():
    _, y_true = make_inputs(200, seed=3)
    y_prob = np.linspace(0.01, 0.99, 200)
    households = pd.Series(np.arange(200) // 2)

    results = compare_paired_predictions(y_true, y_prob, y_prob, households, 50, 0.95, 42)

    assert all(diff.difference == diff.ci_lower == diff.ci_upper == 0 for diff in results)
    assert not any(diff.is_significant for diff in results)


def test_better_model_has_significant_positive_difference():
    generator = np.random.default_rng(4)
    y_true = pd.Series(generator.integers(0, 2, 600))
    better = np.clip(y_true * 0.6 + generator.uniform(0, 0.4, 600), 0, 1)
    random_model = generator.uniform(0, 1, 600)

    results = compare_paired_predictions(
        y_true, better.to_numpy(), random_model, pd.Series(np.arange(600) // 2), 100, 0.95, 42
    )

    assert all(diff.difference > 0 and diff.is_significant for diff in results)


def test_bootstrap_is_reproducible():
    _, y_true = make_inputs(200, seed=5)
    generator = np.random.default_rng(5)
    first, second = generator.uniform(size=200), generator.uniform(size=200)
    households = pd.Series(np.arange(200) // 2)

    assert compare_paired_predictions(y_true, first, second, households, 30, 0.95, 42) == compare_paired_predictions(
        y_true, first, second, households, 30, 0.95, 42
    )


def test_diabetes_excludes_rows_without_blood_values(split_dirs: tuple[Path, Path]):
    split_dir, _ = split_dirs

    dataset = load_baseline_dataset(split_dir, D, KnhanesTrainSet.TRAIN_A)

    assert dataset.excluded_rows == {"train": BLOOD_MISSING_ROWS, "validation": BLOOD_MISSING_ROWS}
    assert dataset.X_train[BLOOD_INPUT_COLUMNS].notna().all(axis=None)
    assert len(dataset.X_validation) == len(dataset.y_validation) == len(dataset.meta_validation)
    assert dataset.meta_validation["ID"].iloc[0] == f"A{BLOOD_MISSING_ROWS}"


def test_hypertension_keeps_rows_without_blood_values(split_dirs: tuple[Path, Path]):
    split_dir, _ = split_dirs

    dataset = load_baseline_dataset(split_dir, H, KnhanesTrainSet.TRAIN_A)

    assert dataset.excluded_rows == {"train": 0, "validation": 0}
    assert dataset.X_train[BLOOD_INPUT_COLUMNS].isna().all(axis=1).sum() == BLOOD_MISSING_ROWS


def test_mismatched_columns_raise(split_dirs: tuple[Path, Path]):
    split_dir, _ = split_dirs
    path = split_dir / D / KnhanesTrainSet.TRAIN_A / "X_validation.parquet"
    pd.read_parquet(path).drop(columns=["나이"]).to_parquet(path, index=False)

    with pytest.raises(KnhanesDataValidationError, match="columns differ"):
        load_baseline_dataset(split_dir, D, KnhanesTrainSet.TRAIN_A)


def test_missing_split_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="split file"):
        load_baseline_dataset(tmp_path, D, KnhanesTrainSet.TRAIN_A)


def test_diagnosed_flags_follow_validation_order(split_dirs: tuple[Path, Path]):
    _, labeled_dir = split_dirs

    flags = load_diagnosed_flags(labeled_dir, H, pd.Series(["A1", "A10", "A0"]))

    assert flags.tolist() == [False, True, True]


def test_unlabeled_validation_id_raises(split_dirs: tuple[Path, Path]):
    _, labeled_dir = split_dirs

    with pytest.raises(KnhanesDataValidationError, match="not labeled"):
        load_diagnosed_flags(labeled_dir, D, pd.Series(["UNKNOWN"]))


@pytest.mark.parametrize(
    "train_b_difference, tg_difference, expected",
    [
        (make_difference(0.01, False), make_difference(0.0, False), KnhanesTrainSet.TRAIN_B),
        (make_difference(-0.02, True), make_difference(0.0, False), KnhanesTrainSet.TRAIN_B),
        (make_difference(0.02, True), make_difference(0.0, False), KnhanesTrainSet.TRAIN_A),
        (make_difference(0.02, True), make_difference(-0.02, True), KnhanesTrainSet.TRAIN_A_TG),
    ],
)
def test_recommendation_prefers_simpler_train_set(
    train_b_difference: PairedDifference, tg_difference: PairedDifference, expected: KnhanesTrainSet
):
    comparisons = {
        str(KnhanesTrainSet.TRAIN_B): [train_b_difference],
        str(KnhanesTrainSet.TRAIN_A_TG): [tg_difference],
    }

    assert recommend_train_set(comparisons) == expected


def test_run_baseline_saves_reports_without_test_split(split_dirs: tuple[Path, Path], tmp_path: Path):
    split_dir, labeled_dir = split_dirs
    report_dir = tmp_path / "reports"
    model_dir = tmp_path / "models"

    report = run_knhanes_baseline(
        split_data_dir=split_dir,
        labeled_data_dir=labeled_dir,
        report_dir=report_dir,
        model_dir=model_dir,
        algorithms=[ModelAlgorithm.LOGISTIC_REGRESSION, ModelAlgorithm.LIGHTGBM],
        resampling_options=[False],
        bootstrap_iterations=20,
    )

    assert report["test_split_used"] is False
    assert set(report["models"]) == {str(model_type) for model_type in ModelType}
    assert "blood_missing_effect" in report["models"][str(D)]
    assert "blood_missing_effect" not in report["models"][str(H)]

    results = pd.read_csv(report_dir / "baseline_results.csv")
    assert set(results["group"]) == {"all", "undiagnosed", "year_2022", "year_2023"}
    assert results["algorithm"].nunique() == 2
    assert len(results) == 2 * len(KnhanesTrainSet) * 2 * 4

    assert json.loads((report_dir / "baseline_report.json").read_text(encoding="utf-8")) == report
    assert "Test는 사용하지 않았습니다" in (report_dir / "baseline_report.md").read_text(encoding="utf-8")
    assert len(list(model_dir.glob("*.pkl"))) == len(ModelType)
    assert (report_dir / D / "metrics.csv").exists()
