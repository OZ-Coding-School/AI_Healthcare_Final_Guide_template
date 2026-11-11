"""
KNHANES 하이퍼파라미터 튜닝, 확률 보정, 위험 등급 임계값 산출을 실행합니다.

데이터 사용 원칙
- 튜닝·보정 방법 선택: Train 안의 가구 단위 교차검증(OOF)
- 튜닝 효과 확인과 임계값 산출: Validation
- Test: 읽지 않습니다. 최종 평가(작업 10)에서 1회만 사용합니다.
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.config import settings
from core.logger import configure_logger
from src.components.knhanes_baseline_evaluator import (
    PairedDifference,
    compare_paired_predictions,
    compute_baseline_metrics,
)
from src.components.knhanes_hyperparameter_tuner import (
    CrossValidationScore,
    KnhanesHyperparameterTuner,
    cross_validate_oof,
    make_household_folds,
    score_oof,
)
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.components.knhanes_probability_calibrator import compute_calibration_metrics, select_calibrator
from src.components.knhanes_risk_threshold import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MODERATE,
    bootstrap_risk_thresholds,
    evaluate_thresholds,
    find_risk_thresholds,
)
from src.components.model_trainer import BinaryClassificationModelTrainer, ModelBundle
from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType
from src.knhanes_training_configs import (
    BASELINE_COMPARED_TRAIN_SETS,
    BASELINE_HYPERPARAMETERS_MAP,
    BASELINE_REFERENCE_TRAIN_SET,
)
from src.knhanes_tuning_configs import (
    RISK_MIN_RECALL,
    RISK_MIN_SPECIFICITY,
    RISK_THRESHOLD_GROUP,
    TUNING_BOOTSTRAP_ITERATIONS,
    TUNING_CANDIDATE_ALGORITHMS_MAP,
    TUNING_CONFIDENCE_LEVEL,
    TUNING_DEFAULT_TRAIN_SET_MAP,
    TUNING_FIXED_HYPERPARAMETERS_MAP,
    TUNING_FOLD_N_JOBS,
    TUNING_N_FOLDS,
    TUNING_N_TRIALS,
    TUNING_PR_AUC_TIE_TOLERANCE,
    TUNING_RANDOM_STATE,
    TUNING_SEARCH_SPACES,
    TUNING_TIMEOUT_SECONDS,
    TUNING_TRAIN_SET_COMPARISON_ALGORITHM_MAP,
)
from src.pipelines.knhanes_data_pipeline import LABELED_DATA_DIR, SPLIT_DATA_DIR
from src.pipelines.knhanes_training_pipeline import (
    HOUSEHOLD_VAR,
    ID_VAR,
    WEIGHT_VAR,
    load_baseline_dataset,
    load_diagnosed_flags,
    recommend_train_set,
)

logger = configure_logger("KNHANES Tuning")

TUNING_REPORT_DIR = settings.MODEL_REPORT_DIR / "knhanes_tuning"
TUNING_MODEL_DIR = settings.MODEL_DIR / "knhanes_tuned"


@dataclass(frozen=True)
class TuningDataset:
    X_train: pd.DataFrame
    y_train: pd.Series
    households_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    meta_validation: pd.DataFrame


@dataclass(frozen=True)
class TuningCandidate:
    algorithm: ModelAlgorithm
    source: str  # baseline: 기본 파라미터, tuned: Optuna 최적 파라미터
    hyperparameters: dict[str, Any]
    score: CrossValidationScore
    completed_trials: int = 0


@dataclass(frozen=True)
class TuningOptions:
    n_trials: int = TUNING_N_TRIALS
    timeout: float | None = TUNING_TIMEOUT_SECONDS
    n_folds: int = TUNING_N_FOLDS
    fold_n_jobs: int = TUNING_FOLD_N_JOBS
    bootstrap_iterations: int = TUNING_BOOTSTRAP_ITERATIONS


def load_tuning_dataset(split_data_dir: Path, model_type: ModelType, train_set: KnhanesTrainSet) -> TuningDataset:
    """Train·Validation과 Train의 가구 ID를 읽고, 두 분할이 가구를 공유하지 않는지 확인합니다."""
    base = load_baseline_dataset(split_data_dir, model_type, train_set)
    meta_train_path = split_data_dir / model_type / train_set / "meta_train.parquet"
    if not meta_train_path.exists():
        raise FileNotFoundError(f"KNHANES split file not found: {meta_train_path}")
    meta_train = pd.read_parquet(meta_train_path)

    for name, meta in [("meta_train", meta_train), ("meta_validation", base.meta_validation)]:
        if HOUSEHOLD_VAR not in meta.columns:
            raise KnhanesDataValidationError(f"{model_type}/{train_set}: {name} has no {HOUSEHOLD_VAR}")
    if len(meta_train) != len(base.X_train):
        raise KnhanesDataValidationError(f"{model_type}/{train_set}: meta_train rows are not aligned")

    shared = set(meta_train[HOUSEHOLD_VAR]) & set(base.meta_validation[HOUSEHOLD_VAR])
    if shared:
        raise KnhanesDataValidationError(f"{model_type}/{train_set}: {len(shared)} households are in both splits")

    return TuningDataset(
        X_train=base.X_train,
        y_train=base.y_train,
        households_train=meta_train[HOUSEHOLD_VAR].reset_index(drop=True),
        X_validation=base.X_validation,
        y_validation=base.y_validation,
        meta_validation=base.meta_validation,
    )


def select_train_set(
    split_data_dir: Path,
    labeled_data_dir: Path,
    model_type: ModelType,
    bootstrap_iterations: int,
) -> tuple[KnhanesTrainSet, dict[str, list[PairedDifference]] | None]:
    """
    비교 대상 질환은 기본 파라미터 모델을 학습 구성별로 학습해 미진단자 Validation에서 비교합니다.
    선택 규칙은 Baseline과 같습니다. Train A가 유의하게 나을 때만 Train A 계열을 고릅니다.
    """
    algorithm = TUNING_TRAIN_SET_COMPARISON_ALGORITHM_MAP.get(model_type)
    if algorithm is None:
        return TUNING_DEFAULT_TRAIN_SET_MAP[model_type], None

    train_sets = [BASELINE_REFERENCE_TRAIN_SET, *BASELINE_COMPARED_TRAIN_SETS]
    datasets = {train_set: load_tuning_dataset(split_data_dir, model_type, train_set) for train_set in train_sets}
    reference = datasets[BASELINE_REFERENCE_TRAIN_SET]
    undiagnosed = ~load_diagnosed_flags(labeled_data_dir, model_type, reference.meta_validation[ID_VAR]).to_numpy()

    probs: dict[KnhanesTrainSet, np.ndarray] = {}
    for train_set, dataset in datasets.items():
        if not dataset.meta_validation[ID_VAR].equals(reference.meta_validation[ID_VAR]):
            raise KnhanesDataValidationError(f"{train_set}: Validation rows differ from the reference")
        bundle = _train_bundle(dataset, algorithm, BASELINE_HYPERPARAMETERS_MAP[algorithm])
        probs[train_set] = bundle.predict_proba(dataset.X_validation)

    comparisons = {
        str(train_set): compare_paired_predictions(
            reference.y_validation[undiagnosed],
            probs[BASELINE_REFERENCE_TRAIN_SET][undiagnosed],
            probs[train_set][undiagnosed],
            reference.meta_validation.loc[undiagnosed, HOUSEHOLD_VAR],
            iterations=bootstrap_iterations,
            confidence_level=TUNING_CONFIDENCE_LEVEL,
            random_state=TUNING_RANDOM_STATE,
        )
        for train_set in BASELINE_COMPARED_TRAIN_SETS
    }
    return recommend_train_set(comparisons), comparisons


def tune_candidates(
    model_type: ModelType,
    dataset: TuningDataset,
    folds: list[tuple[np.ndarray, np.ndarray]],
    algorithms: list[ModelAlgorithm],
    options: TuningOptions,
    report_dir: Path,
) -> list[TuningCandidate]:
    """알고리즘마다 기본 파라미터와 튜닝 결과를 같은 폴드로 평가해 후보로 만듭니다."""
    candidates = []
    for algorithm in algorithms:
        fixed = TUNING_FIXED_HYPERPARAMETERS_MAP[algorithm]
        baseline_params = {**BASELINE_HYPERPARAMETERS_MAP[algorithm], **fixed}
        baseline_oof = cross_validate_oof(
            dataset.X_train,
            dataset.y_train,
            folds,
            algorithm,
            baseline_params,
            TUNING_RANDOM_STATE,
            options.fold_n_jobs,
        )
        candidates.append(
            TuningCandidate(algorithm, "baseline", baseline_params, score_oof(dataset.y_train, baseline_oof, folds))
        )

        started_at = time.perf_counter()
        result = KnhanesHyperparameterTuner(
            dataset.X_train,
            dataset.y_train,
            folds,
            algorithm,
            TUNING_SEARCH_SPACES[algorithm],
            fixed,
            random_state=TUNING_RANDOM_STATE,
            pr_auc_tie_tolerance=TUNING_PR_AUC_TIE_TOLERANCE,
            n_jobs=options.fold_n_jobs,
        ).tune(options.n_trials, options.timeout)
        logger.info(
            "%s/%s: %d trials in %.0fs, CV PR-AUC %.4f",
            model_type,
            algorithm,
            result.completed_trials,
            time.perf_counter() - started_at,
            result.best_score.pr_auc,
        )

        trials_dir = report_dir / model_type
        trials_dir.mkdir(parents=True, exist_ok=True)
        result.trials.to_csv(trials_dir / f"trials_{algorithm}.csv", index=False, encoding="utf-8-sig")
        candidates.append(
            TuningCandidate(algorithm, "tuned", result.best_params, result.best_score, result.completed_trials)
        )
    return candidates


def select_candidate(candidates: list[TuningCandidate], pr_auc_tie_tolerance: float) -> TuningCandidate:
    """CV PR-AUC가 가장 높은 후보를 고르고, 차이가 허용 범위 안이면 Log loss가 낮은 후보를 고릅니다."""
    if not candidates:
        raise ValueError("candidates must not be empty")
    best_pr_auc = max(candidate.score.pr_auc for candidate in candidates)
    tied = [candidate for candidate in candidates if best_pr_auc - candidate.score.pr_auc <= pr_auc_tie_tolerance]
    return min(tied, key=lambda candidate: (candidate.score.log_loss, candidates.index(candidate)))


def run_knhanes_tuning(
    split_data_dir: Path = SPLIT_DATA_DIR,
    labeled_data_dir: Path = LABELED_DATA_DIR,
    report_dir: Path = TUNING_REPORT_DIR,
    model_dir: Path = TUNING_MODEL_DIR,
    model_types: list[ModelType] | None = None,
    algorithms_map: dict[ModelType, list[ModelAlgorithm]] = TUNING_CANDIDATE_ALGORITHMS_MAP,
    options: TuningOptions | None = None,
) -> dict[str, Any]:
    """
    질환마다 다음 순서로 실행합니다.

    1. 학습 구성 결정 (당뇨: 미진단자 Validation 비교, 고혈압: Train B)
    2. Train 가구 단위 CV로 알고리즘별 기본 파라미터와 Optuna 튜닝 비교, 최종 후보 선택
    3. 최종 후보의 OOF 확률로 보정 방법 선택과 보정기 학습
    4. Train 전체로 최종 모델 학습
    5. Validation에서 Baseline 대비 효과와 보정 상태 확인
    6. 미진단자 Validation에서 위험 등급 경계 산출
    7. 보정기와 경계를 담은 ModelBundle과 보고서 저장
    """
    options = options or TuningOptions()
    model_types = model_types or list(ModelType)
    report_dir.mkdir(parents=True, exist_ok=True)

    summaries = {}
    for model_type in model_types:
        summaries[str(model_type)] = _run_model(
            model_type, split_data_dir, labeled_data_dir, report_dir, model_dir, algorithms_map[model_type], options
        )

    report = {
        "evaluated_split": "validation",
        "test_split_used": False,
        "options": asdict(options),
        "risk_criteria": {
            "group": RISK_THRESHOLD_GROUP,
            "min_recall": RISK_MIN_RECALL,
            "min_specificity": RISK_MIN_SPECIFICITY,
        },
        "models": summaries,
    }
    (report_dir / "tuning_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8"
    )
    (report_dir / "tuning_report.md").write_text(render_tuning_report(report), encoding="utf-8")
    logger.info("Saved tuning report to %s", report_dir)
    return report


def _run_model(
    model_type: ModelType,
    split_data_dir: Path,
    labeled_data_dir: Path,
    report_dir: Path,
    model_dir: Path,
    algorithms: list[ModelAlgorithm],
    options: TuningOptions,
) -> dict[str, Any]:
    train_set, train_set_comparisons = select_train_set(
        split_data_dir, labeled_data_dir, model_type, options.bootstrap_iterations
    )
    logger.info("%s: train set %s", model_type, train_set)

    dataset = load_tuning_dataset(split_data_dir, model_type, train_set)
    folds = make_household_folds(dataset.y_train, dataset.households_train, options.n_folds, TUNING_RANDOM_STATE)
    candidates = tune_candidates(model_type, dataset, folds, algorithms, options, report_dir)
    selected = select_candidate(candidates, TUNING_PR_AUC_TIE_TOLERANCE)

    oof_prob = cross_validate_oof(
        dataset.X_train,
        dataset.y_train,
        folds,
        selected.algorithm,
        selected.hyperparameters,
        TUNING_RANDOM_STATE,
        options.fold_n_jobs,
    )
    calibrator, calibration_comparisons = select_calibrator(oof_prob, dataset.y_train, folds)

    bundle = _train_bundle(dataset, selected.algorithm, selected.hyperparameters)
    bundle.calibrator = calibrator
    baseline_bundle = _train_bundle(
        dataset,
        selected.algorithm,
        {**BASELINE_HYPERPARAMETERS_MAP[selected.algorithm], **TUNING_FIXED_HYPERPARAMETERS_MAP[selected.algorithm]},
    )

    raw_prob = np.asarray(bundle.model.predict_proba(bundle.transform(dataset.X_validation)))[:, 1]
    calibrated_prob = bundle.calibrate(raw_prob)
    baseline_prob = baseline_bundle.predict_proba(dataset.X_validation)

    diagnosed = load_diagnosed_flags(labeled_data_dir, model_type, dataset.meta_validation[ID_VAR]).to_numpy()
    masks = {"all": np.ones(len(diagnosed), dtype=bool), "undiagnosed": ~diagnosed}

    validation_metrics = [
        _validation_metrics_row(group, name, dataset, mask, prob)
        for group, mask in masks.items()
        for name, prob in [("baseline", baseline_prob), ("tuned_raw", raw_prob), ("tuned_calibrated", calibrated_prob)]
    ]
    tuning_effect = {
        group: compare_paired_predictions(
            dataset.y_validation[mask],
            calibrated_prob[mask],
            baseline_prob[mask],
            dataset.meta_validation.loc[mask, HOUSEHOLD_VAR],
            iterations=options.bootstrap_iterations,
            confidence_level=TUNING_CONFIDENCE_LEVEL,
            random_state=TUNING_RANDOM_STATE,
        )
        for group, mask in masks.items()
    }

    threshold_mask = masks[RISK_THRESHOLD_GROUP]
    threshold_labels = dataset.y_validation[threshold_mask]
    threshold_prob = calibrated_prob[threshold_mask]
    thresholds = find_risk_thresholds(threshold_labels, threshold_prob, RISK_MIN_RECALL, RISK_MIN_SPECIFICITY)
    threshold_intervals = bootstrap_risk_thresholds(
        threshold_labels,
        threshold_prob,
        dataset.meta_validation.loc[threshold_mask, HOUSEHOLD_VAR],
        RISK_MIN_RECALL,
        RISK_MIN_SPECIFICITY,
        options.bootstrap_iterations,
        TUNING_CONFIDENCE_LEVEL,
        TUNING_RANDOM_STATE,
    )
    threshold_performance = {
        group: evaluate_thresholds(dataset.y_validation[mask], calibrated_prob[mask], thresholds)
        for group, mask in masks.items()
    }
    level_shares = {
        group: {
            level: float(np.mean(thresholds.classify(calibrated_prob[mask]) == level))
            for level in [RISK_LEVEL_LOW, RISK_LEVEL_MODERATE, RISK_LEVEL_HIGH]
        }
        for group, mask in masks.items()
    }

    bundle.risk_thresholds = thresholds.to_dict()
    bundle.threshold = thresholds.moderate
    saved_model_path = model_dir / f"{model_type}_{train_set}_{selected.algorithm}.pkl"
    bundle.save(saved_model_path)

    return {
        "train_set": str(train_set),
        "train_set_comparisons_undiagnosed": _serialize_differences(train_set_comparisons)
        if train_set_comparisons is not None
        else None,
        "candidates": [
            {
                "algorithm": str(candidate.algorithm),
                "source": candidate.source,
                "cv_pr_auc": candidate.score.pr_auc,
                "cv_log_loss": candidate.score.log_loss,
                "cv_fold_pr_aucs": candidate.score.fold_pr_aucs,
                "completed_trials": candidate.completed_trials,
                "hyperparameters": candidate.hyperparameters,
            }
            for candidate in candidates
        ],
        "selected": {
            "algorithm": str(selected.algorithm),
            "source": selected.source,
            "hyperparameters": selected.hyperparameters,
        },
        "calibration": {
            "selected_method": calibrator.method,
            "comparisons": [asdict(comparison) for comparison in calibration_comparisons],
        },
        "validation_metrics": validation_metrics,
        "tuning_effect_vs_baseline": _serialize_differences(tuning_effect),
        "risk_thresholds": thresholds.to_dict(),
        "risk_threshold_intervals": [asdict(interval) for interval in threshold_intervals],
        "risk_threshold_performance": {
            group: [asdict(performance) for performance in performances]
            for group, performances in threshold_performance.items()
        },
        "risk_level_shares": level_shares,
        "saved_model_path": str(saved_model_path),
    }


def _train_bundle(dataset: TuningDataset, algorithm: ModelAlgorithm, hyperparameters: dict[str, Any]) -> ModelBundle:
    return BinaryClassificationModelTrainer(
        x_train=dataset.X_train,
        y_train=dataset.y_train,
        algorithm=algorithm,
        random_state=TUNING_RANDOM_STATE,
        hyperparameters=hyperparameters,
    ).train()


def _validation_metrics_row(
    group: str, model: str, dataset: TuningDataset, mask: np.ndarray, prob: np.ndarray
) -> dict[str, Any]:
    y_true = dataset.y_validation[mask]
    ranking = compute_baseline_metrics(y_true, prob[mask], dataset.meta_validation.loc[mask, WEIGHT_VAR])
    calibration = compute_calibration_metrics(y_true, prob[mask])
    return {
        "group": group,
        "model": model,
        **asdict(ranking),
        "log_loss": calibration.log_loss,
        "ece": calibration.ece,
    }


def _serialize_differences(differences: dict[str, list[PairedDifference]]) -> dict[str, list[dict[str, Any]]]:
    return {
        key: [{**asdict(diff), "is_significant": diff.is_significant} for diff in values]
        for key, values in differences.items()
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def render_tuning_report(report: dict[str, Any]) -> str:
    criteria = report["risk_criteria"]
    options = report["options"]
    lines = [
        "# KNHANES 튜닝·보정·임계값 보고서",
        "",
        "- **튜닝:** Train 안의 가구 단위 "
        f"{options['n_folds']}-fold 교차검증, 알고리즘당 최대 {options['n_trials']} trial",
        "- **보정 방법 선택:** Train OOF 확률 안에서 교차 적합한 Log loss",
        "- **확인·임계값:** Validation (2022~2023년). Test는 사용하지 않았습니다.",
        f"- **위험 등급 기준:** {criteria['group']} 집단, MODERATE 경계 재현율 {criteria['min_recall']:.2f} 이상, "
        f"HIGH 경계 특이도 {criteria['min_specificity']:.2f} 이상",
        f"- **신뢰구간:** 가구 단위 부트스트랩 {options['bootstrap_iterations']}회, 95%",
    ]
    for model_type, summary in report["models"].items():
        selected = summary["selected"]
        lines += [
            "",
            f"## {model_type}",
            "",
            f"- **학습 구성:** {summary['train_set']}",
            f"- **선택 모델:** {selected['algorithm']} ({selected['source']})",
            f"- **보정 방법:** {summary['calibration']['selected_method']}",
            f"- **저장 경로:** `{summary['saved_model_path']}`",
        ]

        if summary["train_set_comparisons_undiagnosed"]:
            lines += [
                "",
                "### 학습 구성 비교 (미진단자, train_a - 비교 구성)",
                "",
                "| 비교 구성 | 지표 | train_a | 비교 구성 값 | 차이 | 95% 신뢰구간 |",
                "|---|---|---:|---:|---:|---:|",
            ]
            for train_set, differences in summary["train_set_comparisons_undiagnosed"].items():
                lines += [_difference_line(train_set, diff) for diff in differences]

        lines += [
            "",
            "### CV 후보 (Train)",
            "",
            "| 알고리즘 | 파라미터 | CV PR-AUC | CV Log loss | 완료 trial |",
            "|---|---|---:|---:|---:|",
        ]
        for candidate in summary["candidates"]:
            lines.append(
                f"| {candidate['algorithm']} | {candidate['source']} | {candidate['cv_pr_auc']:.4f} "
                f"| {candidate['cv_log_loss']:.4f} | {candidate['completed_trials']} |"
            )

        lines += [
            "",
            "### 보정 방법 비교 (Train OOF)",
            "",
            "| 방법 | Log loss | Brier |",
            "|---|---:|---:|",
        ]
        for comparison in summary["calibration"]["comparisons"]:
            lines.append(f"| {comparison['method']} | {comparison['cv_log_loss']:.4f} | {comparison['cv_brier']:.4f} |")

        lines += [
            "",
            "### Validation 성능",
            "",
            "| 집단 | 모델 | 양성률 | 평균 예측 | ROC-AUC | PR-AUC | Brier | Log loss | ECE |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in summary["validation_metrics"]:
            lines.append(
                f"| {row['group']} | {row['model']} | {row['positive_rate']:.3f} | {row['mean_predicted']:.3f} "
                f"| {row['roc_auc']:.3f} | {row['pr_auc']:.3f} | {row['brier']:.4f} | {row['log_loss']:.4f} "
                f"| {row['ece']:.4f} |"
            )

        lines += [
            "",
            "### 튜닝 효과 (보정 모델 - Baseline)",
            "",
            "| 집단 | 지표 | 보정 모델 | Baseline | 차이 | 95% 신뢰구간 |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for group, differences in summary["tuning_effect_vs_baseline"].items():
            lines += [_difference_line(group, diff) for diff in differences]

        lines += [
            "",
            "### 위험 등급 경계",
            "",
            "| 등급 | 경계 확률 | 95% 신뢰구간 |",
            "|---|---:|---:|",
        ]
        for interval in summary["risk_threshold_intervals"]:
            lines.append(
                f"| {interval['level']} | {interval['threshold']:.4f} "
                f"| {interval['ci_lower']:.4f} ~ {interval['ci_upper']:.4f} |"
            )

        lines += [
            "",
            "| 집단 | 경계 | 재현율 | 특이도 | 정밀도 | 해당 비율 |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for group, performances in summary["risk_threshold_performance"].items():
            for performance in performances:
                lines.append(
                    f"| {group} | {performance['level']} 이상 | {performance['recall']:.3f} "
                    f"| {performance['specificity']:.3f} | {performance['precision']:.3f} "
                    f"| {performance['flagged_rate']:.3f} |"
                )

        lines += ["", "| 집단 | LOW | MODERATE | HIGH |", "|---|---:|---:|---:|"]
        for group, shares in summary["risk_level_shares"].items():
            lines.append(
                f"| {group} | {shares[RISK_LEVEL_LOW]:.3f} | {shares[RISK_LEVEL_MODERATE]:.3f} "
                f"| {shares[RISK_LEVEL_HIGH]:.3f} |"
            )
    return "\n".join(lines) + "\n"


def _difference_line(label: str, diff: dict[str, Any]) -> str:
    return (
        f"| {label} | {diff['metric']} | {diff['reference']:.3f} | {diff['compared']:.3f} "
        f"| {diff['difference']:+.3f} | {diff['ci_lower']:+.3f} ~ {diff['ci_upper']:+.3f} |"
    )


if __name__ == "__main__":
    run_knhanes_tuning()
