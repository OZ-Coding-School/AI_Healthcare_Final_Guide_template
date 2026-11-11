import json
from pathlib import Path

import joblib
import numpy as np
import optuna
import pandas as pd
import pytest

from src.components.knhanes_hyperparameter_tuner import (
    CrossValidationScore,
    KnhanesHyperparameterTuner,
    cross_validate_oof,
    make_household_folds,
    select_best_trial,
)
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.components.knhanes_probability_calibrator import (
    ProbabilityCalibrator,
    expected_calibration_error,
    select_calibrator,
)
from src.components.knhanes_risk_threshold import (
    RiskThresholds,
    bootstrap_risk_thresholds,
    evaluate_thresholds,
    find_risk_thresholds,
)
from src.components.model_evaluator import ModelEvaluator
from src.components.model_trainer import BinaryClassificationModelTrainer, ModelBundle
from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType
from src.knhanes_tuning_configs import FloatParam, IntParam
from src.pipelines.knhanes_tuning_pipeline import (
    TuningCandidate,
    TuningOptions,
    load_tuning_dataset,
    run_knhanes_tuning,
    select_candidate,
    select_train_set,
)

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK
LR = ModelAlgorithm.LOGISTIC_REGRESSION

TRAIN_ROWS, VALIDATION_ROWS = 240, 160
FAST_OPTIONS = TuningOptions(n_trials=3, timeout=None, n_folds=3, fold_n_jobs=1, bootstrap_iterations=20)


def make_inputs(rows: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    generator = np.random.default_rng(seed)
    signal = generator.normal(size=rows)
    X = pd.DataFrame(
        {
            "나이": 50 + 10 * signal + generator.normal(size=rows),
            "총콜레스테롤": generator.normal(100, 10, rows),
            "AST": generator.normal(30, 5, rows),
        }
    )
    X["성별"] = pd.Categorical(generator.choice(["M", "F"], rows))
    y = pd.Series((signal + generator.normal(scale=0.7, size=rows) > 0.5).astype(int), name="disease_label")
    return X, y


def make_meta(rows: int, prefix: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": [f"{prefix}{index}" for index in range(rows)],
            "ID_fam": [f"{prefix}F{index // 2}" for index in range(rows)],
            "year": [2022.0, 2023.0] * (rows // 2),
            "wt_itvex": 1.0,
            "wt_tot": 1.0,
            "kstrata": 1,
            "psu": 1,
        }
    )


@pytest.fixture
def split_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Test 파일을 만들지 않아 파이프라인이 Test를 읽으면 실패하도록 합니다."""
    split_dir = tmp_path / "split"
    labeled_dir = tmp_path / "labeled"
    labeled_dir.mkdir()

    X_validation, y_validation = make_inputs(VALIDATION_ROWS, seed=2)
    meta_validation = make_meta(VALIDATION_ROWS, "V")
    meta_train = make_meta(TRAIN_ROWS, "T")

    for model_type in ModelType:
        for train_set in KnhanesTrainSet:
            output_dir = split_dir / model_type / train_set
            output_dir.mkdir(parents=True)
            X_train, y_train = make_inputs(TRAIN_ROWS, seed=1)
            X_train.to_parquet(output_dir / "X_train.parquet", index=False)
            y_train.to_frame().to_parquet(output_dir / "y_train.parquet", index=False)
            meta_train.to_parquet(output_dir / "meta_train.parquet", index=False)
            X_validation.to_parquet(output_dir / "X_validation.parquet", index=False)
            y_validation.to_frame().to_parquet(output_dir / "y_validation.parquet", index=False)
            meta_validation.to_parquet(output_dir / "meta_validation.parquet", index=False)

    diagnosed = np.arange(VALIDATION_ROWS) % 10 == 0
    pd.DataFrame(
        {"ID": meta_validation["ID"], "DE1_dg": np.where(diagnosed, 1.0, 0.0), "DE1_31": 0.0, "DE1_32": 0.0}
    ).to_parquet(labeled_dir / f"{D}.parquet", index=False)
    pd.DataFrame({"ID": meta_validation["ID"], "DI1_pr": np.where(diagnosed, 1.0, 0.0), "DI1_2": 5.0}).to_parquet(
        labeled_dir / f"{H}.parquet", index=False
    )
    return split_dir, labeled_dir


@pytest.fixture
def train_data() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    X, y = make_inputs(TRAIN_ROWS, seed=1)
    return X, y, make_meta(TRAIN_ROWS, "T")["ID_fam"]


def make_completed_trial(number: int, value: float, log_loss: float) -> optuna.trial.FrozenTrial:
    trial = optuna.trial.create_trial(
        value=value,
        params={"C": 1.0},
        distributions={"C": optuna.distributions.FloatDistribution(1e-3, 100.0, log=True)},
        user_attrs={"log_loss": log_loss, "fold_pr_aucs": [value]},
    )
    trial.number = number
    return trial


# --- 가구 단위 폴드 ---


def test_household_folds_do_not_share_households(train_data):
    _, y, households = train_data

    folds = make_household_folds(y, households, n_folds=3, random_state=42)

    covered = np.concatenate([validation_idx for _, validation_idx in folds])
    assert sorted(covered) == list(range(len(y)))
    for train_idx, validation_idx in folds:
        assert not set(households.iloc[train_idx]) & set(households.iloc[validation_idx])


def test_household_folds_are_reproducible(train_data):
    _, y, households = train_data

    first = make_household_folds(y, households, 3, 42)
    second = make_household_folds(y, households, 3, 42)

    assert all(np.array_equal(a[1], b[1]) for a, b in zip(first, second, strict=True))


@pytest.mark.parametrize(
    "y, households, error",
    [
        (pd.Series([1] * 6), pd.Series(range(6)), KnhanesDataValidationError),
        (pd.Series([0, 1] * 3), pd.Series([0, 0, 0, 1, 1, 1]), KnhanesDataValidationError),
        (pd.Series([0, 1] * 3), pd.Series([0, 1, 2, 3, None, 5]), KnhanesDataValidationError),
        (pd.Series([0, 1] * 3), pd.Series(range(5)), KnhanesDataValidationError),
    ],
)
def test_household_folds_reject_invalid_input(y, households, error):
    with pytest.raises(error):
        make_household_folds(y, households, n_folds=3, random_state=42)


def test_oof_is_identical_with_parallel_folds(train_data):
    X, y, households = train_data
    folds = make_household_folds(y, households, 3, 42)

    serial = cross_validate_oof(X, y, folds, LR, {"max_iter": 2000}, 42, n_jobs=1)
    parallel = cross_validate_oof(X, y, folds, LR, {"max_iter": 2000}, 42, n_jobs=2)

    assert serial.shape == (len(y),)
    assert ((serial >= 0) & (serial <= 1)).all()
    np.testing.assert_allclose(serial, parallel)


# --- Optuna 튜너 ---


def make_tuner(train_data, search_space=None, fixed=None) -> KnhanesHyperparameterTuner:
    X, y, households = train_data
    return KnhanesHyperparameterTuner(
        X,
        y,
        make_household_folds(y, households, 3, 42),
        LR,
        search_space or {"C": FloatParam(1e-2, 10.0, log=True)},
        fixed if fixed is not None else {"max_iter": 2000},
        random_state=42,
        pr_auc_tie_tolerance=0.002,
    )


def test_tuner_returns_fixed_and_searched_parameters(train_data):
    result = make_tuner(train_data).tune(n_trials=3)

    assert result.completed_trials == 3
    assert result.best_params["max_iter"] == 2000
    assert 1e-2 <= result.best_params["C"] <= 10.0
    assert 0 <= result.best_score.pr_auc <= 1
    assert len(result.best_score.fold_pr_aucs) == 3
    assert len(result.trials) == 3


def test_tuner_is_reproducible(train_data):
    assert make_tuner(train_data).tune(3).best_params == make_tuner(train_data).tune(3).best_params


def test_tuner_rejects_overlapping_parameters(train_data):
    with pytest.raises(ValueError, match="both searched and fixed"):
        make_tuner(train_data, search_space={"max_iter": IntParam(100, 200)})


def test_best_trial_prefers_lower_log_loss_within_tolerance():
    trials = [
        make_completed_trial(0, 0.800, 0.40),
        make_completed_trial(1, 0.799, 0.35),
        make_completed_trial(2, 0.790, 0.30),
    ]

    assert select_best_trial(trials, pr_auc_tie_tolerance=0.002).number == 1
    assert select_best_trial(trials, pr_auc_tie_tolerance=0.0).number == 0


def test_candidate_selection_uses_same_tie_rule():
    def candidate(source: str, pr_auc: float, loss: float) -> TuningCandidate:
        return TuningCandidate(LR, source, {}, CrossValidationScore(pr_auc, loss, [pr_auc]))

    candidates = [candidate("baseline", 0.700, 0.50), candidate("tuned", 0.701, 0.55)]

    assert select_candidate(candidates, 0.002).source == "baseline"
    assert select_candidate(candidates, 0.0).source == "tuned"


# --- 확률 보정 ---


def make_overconfident(rows: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    true_prob = generator.uniform(0.05, 0.6, rows)
    labels = (generator.uniform(size=rows) < true_prob).astype(int)
    raw_prob = true_prob**0.3  # 실제보다 높게 예측하는 모델
    return raw_prob, labels


@pytest.mark.parametrize("method", ["sigmoid", "isotonic"])
def test_calibration_reduces_overconfidence(method: str):
    raw_prob, labels = make_overconfident(2000, seed=1)

    calibrated = ProbabilityCalibrator(method).fit(raw_prob, labels).transform(raw_prob)

    assert ((calibrated > 0) & (calibrated < 1)).all()
    assert abs(calibrated.mean() - labels.mean()) < abs(raw_prob.mean() - labels.mean())
    order = np.argsort(raw_prob)
    assert (np.diff(calibrated[order]) >= -1e-12).all()


def test_none_calibration_only_clips():
    calibrator = ProbabilityCalibrator("none").fit(np.array([0.2, 0.8]), np.array([0, 1]))

    np.testing.assert_allclose(calibrator.transform(np.array([0.0, 0.5, 1.0])), [1e-4, 0.5, 1 - 1e-4])


def test_calibrator_validates_usage():
    with pytest.raises(ValueError, match="Unknown calibration method"):
        ProbabilityCalibrator("beta")
    with pytest.raises(RuntimeError, match="fitted"):
        ProbabilityCalibrator("sigmoid").transform(np.array([0.5]))
    with pytest.raises(KnhanesDataValidationError):
        ProbabilityCalibrator("sigmoid").fit(np.array([0.2, 0.4]), np.array([1, 1]))
    with pytest.raises(KnhanesDataValidationError):
        ProbabilityCalibrator("sigmoid").fit(np.array([0.2, 1.4]), np.array([0, 1]))


def test_select_calibrator_rejects_uncalibrated_probabilities():
    raw_prob, labels = make_overconfident(1200, seed=2)
    y = pd.Series(labels)
    folds = make_household_folds(y, pd.Series(np.arange(len(y))), 3, 42)

    calibrator, comparisons = select_calibrator(raw_prob, y, folds)

    assert [comparison.method for comparison in comparisons] == ["none", "sigmoid", "isotonic"]
    assert calibrator.method != "none"
    assert calibrator.is_fitted


def test_expected_calibration_error():
    labels = np.array([0, 1, 0, 1])

    assert expected_calibration_error(labels, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.0)
    assert expected_calibration_error(labels, np.array([0.9, 0.9, 0.9, 0.9])) == pytest.approx(0.4)


# --- 위험 등급 임계값 ---


def make_scores(seed: int, rows: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    labels = (generator.uniform(size=rows) < 0.2).astype(int)
    prob = np.clip(0.15 + 0.25 * labels + generator.normal(0, 0.12, rows), 0.001, 0.999)
    return labels, prob


def test_thresholds_meet_recall_and_specificity():
    labels, prob = make_scores(seed=3)

    thresholds = find_risk_thresholds(labels, prob, min_recall=0.9, min_specificity=0.9)
    moderate, high = evaluate_thresholds(labels, prob, thresholds)

    assert thresholds.moderate <= thresholds.high
    assert moderate.recall >= 0.9
    assert high.specificity >= 0.9
    # 경계는 조건을 만족하는 가장 엄격한 값이어야 합니다.
    assert (prob[labels == 1] >= np.nextafter(thresholds.moderate, 1)).mean() < 0.9


def test_thresholds_on_small_example():
    labels = np.array([0, 0, 0, 0, 1, 1])
    prob = np.array([0.1, 0.2, 0.3, 0.6, 0.4, 0.9])

    thresholds = find_risk_thresholds(labels, prob, min_recall=1.0, min_specificity=1.0)

    assert thresholds.moderate == pytest.approx(0.4)
    assert 0.6 < thresholds.high < 0.6 + 1e-12
    assert thresholds.classify(np.array([0.1, 0.4, 0.95])).tolist() == ["LOW", "MODERATE", "HIGH"]


def test_high_threshold_never_falls_below_moderate():
    labels = np.array([0, 0, 0, 0, 1, 1])
    prob = np.array([0.1, 0.2, 0.3, 0.6, 0.4, 0.9])

    thresholds = find_risk_thresholds(labels, prob, min_recall=1.0, min_specificity=0.75)

    assert thresholds.moderate == thresholds.high == pytest.approx(0.4)


def test_risk_thresholds_validate_order_and_input():
    with pytest.raises(ValueError):
        RiskThresholds(moderate=0.5, high=0.2)
    with pytest.raises(ValueError):
        find_risk_thresholds(np.array([0, 1]), np.array([0.1, 0.9]), min_recall=0, min_specificity=0.9)
    with pytest.raises(KnhanesDataValidationError):
        find_risk_thresholds(np.array([1, 1]), np.array([0.1, 0.9]), 0.9, 0.9)


def test_threshold_bootstrap_is_reproducible_and_ordered():
    labels, prob = make_scores(seed=4, rows=400)
    households = pd.Series(np.arange(400) // 2)

    first = bootstrap_risk_thresholds(labels, prob, households, 0.9, 0.9, 30, 0.95, 42)
    second = bootstrap_risk_thresholds(labels, prob, households, 0.9, 0.9, 30, 0.95, 42)

    assert first == second
    assert all(interval.ci_lower <= interval.ci_upper for interval in first)


# --- ModelBundle 보정 ---


def make_bundle(train_data) -> ModelBundle:
    X, y, _ = train_data
    return BinaryClassificationModelTrainer(X, y, algorithm=LR, hyperparameters={"max_iter": 2000}).train()


def test_bundle_predict_proba_applies_calibrator(train_data):
    X, y, _ = train_data
    bundle = make_bundle(train_data)
    raw = bundle.predict_proba(X)

    bundle.calibrator = ProbabilityCalibrator("isotonic").fit(raw, y)

    np.testing.assert_allclose(bundle.predict_proba(X), bundle.calibrator.transform(raw))
    assert not np.allclose(bundle.predict_proba(X), raw)


def test_bundle_round_trip_keeps_calibrator_and_thresholds(train_data, tmp_path: Path):
    X, y, _ = train_data
    bundle = make_bundle(train_data)
    bundle.calibrator = ProbabilityCalibrator("sigmoid").fit(bundle.predict_proba(X), y)
    bundle.risk_thresholds = {"moderate": 0.1, "high": 0.4}

    bundle.save(tmp_path / "bundle.pkl")
    loaded = ModelBundle.load(tmp_path / "bundle.pkl")

    assert loaded.risk_thresholds == {"moderate": 0.1, "high": 0.4}
    np.testing.assert_allclose(loaded.predict_proba(X), bundle.predict_proba(X))


def test_legacy_bundle_without_calibrator_loads(train_data, tmp_path: Path):
    X, _, _ = train_data
    bundle = make_bundle(train_data)
    legacy = {
        "model": bundle.model,
        "preprocessor": bundle.preprocessor,
        "post_preprocessor": None,
        "feature_names": bundle.feature_names,
        "threshold": 0.5,
    }
    joblib.dump(legacy, tmp_path / "legacy.pkl")

    loaded = ModelBundle.load(tmp_path / "legacy.pkl")

    assert loaded.calibrator is None
    assert loaded.risk_thresholds is None
    np.testing.assert_allclose(loaded.predict_proba(X), bundle.model.predict_proba(bundle.transform(X))[:, 1])


def test_model_evaluator_uses_calibrated_probability(train_data, tmp_path: Path):
    X, y, _ = train_data
    bundle = make_bundle(train_data)
    bundle.calibrator = ProbabilityCalibrator("isotonic").fit(bundle.predict_proba(X), y)

    result = ModelEvaluator.from_bundle(bundle, X, y, tmp_path).evaluate()

    np.testing.assert_allclose(result.y_prob, bundle.predict_proba(X))


# --- 파이프라인 ---


def test_load_tuning_dataset_reads_train_households(split_dirs):
    split_dir, _ = split_dirs

    dataset = load_tuning_dataset(split_dir, D, KnhanesTrainSet.TRAIN_B)

    assert len(dataset.households_train) == len(dataset.X_train) == TRAIN_ROWS


def test_load_tuning_dataset_rejects_shared_households(split_dirs):
    split_dir, _ = split_dirs
    path = split_dir / D / KnhanesTrainSet.TRAIN_B / "meta_train.parquet"
    meta_train = pd.read_parquet(path)
    meta_train.loc[0, "ID_fam"] = "VF0"
    meta_train.to_parquet(path, index=False)

    with pytest.raises(KnhanesDataValidationError, match="households are in both splits"):
        load_tuning_dataset(split_dir, D, KnhanesTrainSet.TRAIN_B)


def test_load_tuning_dataset_requires_meta_train(split_dirs):
    split_dir, _ = split_dirs
    (split_dir / D / KnhanesTrainSet.TRAIN_B / "meta_train.parquet").unlink()

    with pytest.raises(FileNotFoundError, match="meta_train"):
        load_tuning_dataset(split_dir, D, KnhanesTrainSet.TRAIN_B)


def test_train_set_selection(split_dirs):
    split_dir, labeled_dir = split_dirs

    hypertension_set, hypertension_comparisons = select_train_set(split_dir, labeled_dir, H, 20)
    diabetes_set, diabetes_comparisons = select_train_set(split_dir, labeled_dir, D, 20)

    assert hypertension_set == KnhanesTrainSet.TRAIN_B
    assert hypertension_comparisons is None
    # 학습 구성 데이터가 모두 같으므로 차이가 없고, 더 단순한 Train B를 고릅니다.
    assert diabetes_set == KnhanesTrainSet.TRAIN_B
    assert set(diabetes_comparisons) == {str(KnhanesTrainSet.TRAIN_B), str(KnhanesTrainSet.TRAIN_A_TG)}


def test_run_tuning_saves_calibrated_bundle_without_test_split(split_dirs, tmp_path: Path):
    split_dir, labeled_dir = split_dirs
    report_dir = tmp_path / "reports"
    model_dir = tmp_path / "models"

    report = run_knhanes_tuning(
        split_data_dir=split_dir,
        labeled_data_dir=labeled_dir,
        report_dir=report_dir,
        model_dir=model_dir,
        algorithms_map={D: [LR], H: [LR]},
        options=FAST_OPTIONS,
    )

    assert report["test_split_used"] is False
    assert json.loads((report_dir / "tuning_report.json").read_text(encoding="utf-8")) == json.loads(json.dumps(report))
    assert "Test는 사용하지 않았습니다" in (report_dir / "tuning_report.md").read_text(encoding="utf-8")

    for model_type in ModelType:
        summary = report["models"][str(model_type)]
        assert {candidate["source"] for candidate in summary["candidates"]} == {"baseline", "tuned"}
        assert (report_dir / model_type / f"trials_{LR}.csv").exists()
        assert {row["model"] for row in summary["validation_metrics"]} == {
            "baseline",
            "tuned_raw",
            "tuned_calibrated",
        }

        bundle = ModelBundle.load(summary["saved_model_path"])
        assert bundle.calibrator is not None
        assert bundle.risk_thresholds == summary["risk_thresholds"]
        assert bundle.risk_thresholds["moderate"] <= bundle.risk_thresholds["high"]
        assert bundle.threshold == bundle.risk_thresholds["moderate"]
        shares = summary["risk_level_shares"]["all"]
        assert sum(shares.values()) == pytest.approx(1.0)
