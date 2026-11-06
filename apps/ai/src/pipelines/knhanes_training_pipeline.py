"""
KNHANES Baseline 학습과 학습 구성 비교를 실행합니다.

Test 분할은 최종 평가에 1회만 쓰기 위해 이 파이프라인에서 읽지 않습니다.
모든 비교와 선택은 학습 구성이 공유하는 Validation으로만 수행합니다.
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
    BaselineMetrics,
    PairedDifference,
    compare_paired_predictions,
    compute_baseline_metrics,
)
from src.components.knhanes_multi_year_loader import YEAR_VAR, KnhanesDataValidationError
from src.components.model_evaluator import ModelEvaluator
from src.components.model_trainer import BinaryClassificationModelTrainer, ModelBundle
from src.enums import KnhanesTrainSet, ModelAlgorithm, ModelType
from src.knhanes_training_configs import (
    BASELINE_ALGORITHMS,
    BASELINE_BOOTSTRAP_ITERATIONS,
    BASELINE_COMPARED_TRAIN_SETS,
    BASELINE_CONFIDENCE_LEVEL,
    BASELINE_HYPERPARAMETERS_MAP,
    BASELINE_RANDOM_STATE,
    BASELINE_REFERENCE_TRAIN_SET,
    BASELINE_RESAMPLING_OPTIONS,
    MODEL_DIAGNOSED_CODES_MAP,
)
from src.pipelines.knhanes_data_pipeline import LABELED_DATA_DIR, SPLIT_DATA_DIR

logger = configure_logger("KNHANES Training")

ID_VAR = "ID"
HOUSEHOLD_VAR = "ID_fam"
WEIGHT_VAR = "wt_itvex"

BASELINE_REPORT_DIR = settings.MODEL_REPORT_DIR / "knhanes_baseline"
BASELINE_MODEL_DIR = settings.MODEL_DIR / "knhanes_baseline"


@dataclass(frozen=True)
class BaselineDataset:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    meta_validation: pd.DataFrame


@dataclass(frozen=True)
class BaselineExperiment:
    model_type: ModelType
    train_set: KnhanesTrainSet
    algorithm: ModelAlgorithm
    use_resampling: bool


@dataclass(frozen=True)
class BaselineRun:
    experiment: BaselineExperiment
    bundle: ModelBundle
    validation_prob: np.ndarray
    dataset: BaselineDataset
    seconds: float


def load_baseline_dataset(split_data_dir: Path, model_type: ModelType, train_set: KnhanesTrainSet) -> BaselineDataset:
    """저장된 분할에서 Train과 Validation만 읽고 입력 구조를 검증합니다."""
    split_dir = split_data_dir / model_type / train_set
    X_train = _read_split_file(split_dir, "X_train")
    y_train = _read_split_file(split_dir, "y_train").iloc[:, 0]
    X_validation = _read_split_file(split_dir, "X_validation")
    y_validation = _read_split_file(split_dir, "y_validation").iloc[:, 0]
    meta_validation = _read_split_file(split_dir, "meta_validation")

    if X_train.columns.tolist() != X_validation.columns.tolist():
        raise KnhanesDataValidationError(f"{model_type}/{train_set}: Train and Validation columns differ")
    if len(X_train) != len(y_train) or not len(X_validation) == len(y_validation) == len(meta_validation):
        raise KnhanesDataValidationError(f"{model_type}/{train_set}: split rows are not aligned")

    return BaselineDataset(X_train, y_train, X_validation, y_validation, meta_validation)


def load_diagnosed_flags(labeled_data_dir: Path, model_type: ModelType, ids: pd.Series) -> pd.Series:
    """Validation 행별로 이미 진단·치료 중인 응답자인지 반환합니다. 입력이 아닌 평가 구분에만 씁니다."""
    labeled_path = labeled_data_dir / f"{model_type}.parquet"
    if not labeled_path.exists():
        raise FileNotFoundError(f"Labeled KNHANES data not found: {labeled_path}")

    codes_map = MODEL_DIAGNOSED_CODES_MAP[model_type]
    labeled_df = pd.read_parquet(labeled_path, columns=[ID_VAR, *codes_map]).set_index(ID_VAR)
    diagnosed = pd.Series(False, index=labeled_df.index)
    for var_name, codes in codes_map.items():
        diagnosed |= labeled_df[var_name].isin(codes)

    missing_ids = ~ids.isin(diagnosed.index)
    if missing_ids.any():
        raise KnhanesDataValidationError(f"{model_type}: {int(missing_ids.sum())} validation IDs are not labeled")
    return pd.Series(diagnosed.loc[ids].to_numpy(), index=ids.index, name="diagnosed")


def train_baseline(experiment: BaselineExperiment, dataset: BaselineDataset) -> BaselineRun:
    started_at = time.perf_counter()
    bundle = BinaryClassificationModelTrainer(
        x_train=dataset.X_train,
        y_train=dataset.y_train,
        algorithm=experiment.algorithm,
        use_resampling=experiment.use_resampling,
        random_state=BASELINE_RANDOM_STATE,
        hyperparameters=BASELINE_HYPERPARAMETERS_MAP[experiment.algorithm],
    ).train()
    validation_prob = _predict_probability(bundle, dataset.X_validation)
    return BaselineRun(experiment, bundle, validation_prob, dataset, time.perf_counter() - started_at)


def evaluate_baseline(run: BaselineRun, diagnosed: pd.Series) -> list[dict[str, Any]]:
    """전체, 연도별, 미진단자의 Validation 지표를 행 단위로 반환합니다."""
    dataset = run.dataset
    years = dataset.meta_validation[YEAR_VAR].astype(int)
    masks = {"all": pd.Series(True, index=years.index), "undiagnosed": ~diagnosed}
    masks.update({f"year_{year}": years.eq(year) for year in sorted(years.unique())})

    base_row = {
        "model_type": str(run.experiment.model_type),
        "train_set": str(run.experiment.train_set),
        "algorithm": str(run.experiment.algorithm),
        "use_resampling": run.experiment.use_resampling,
        "train_rows": len(dataset.y_train),
        "train_positive_rate": float(dataset.y_train.mean()),
        "seconds": round(run.seconds, 2),
    }

    rows = []
    for group, mask in masks.items():
        metrics: BaselineMetrics = compute_baseline_metrics(
            dataset.y_validation[mask],
            run.validation_prob[mask.to_numpy()],
            dataset.meta_validation.loc[mask, WEIGHT_VAR],
        )
        rows.append({**base_row, "group": group, **asdict(metrics)})
    return rows


def compare_train_sets(runs: dict[KnhanesTrainSet, BaselineRun], bootstrap_iterations: int) -> dict[str, list[Any]]:
    """같은 알고리즘의 학습 구성별 예측을 Train A 기준으로 비교합니다."""
    reference = runs[BASELINE_REFERENCE_TRAIN_SET]
    comparisons: dict[str, list[PairedDifference]] = {}
    for train_set in BASELINE_COMPARED_TRAIN_SETS:
        compared = runs[train_set]
        if not reference.dataset.meta_validation[ID_VAR].equals(compared.dataset.meta_validation[ID_VAR]):
            raise KnhanesDataValidationError(f"{train_set}: Validation rows differ from the reference")
        comparisons[str(train_set)] = compare_paired_predictions(
            reference.dataset.y_validation,
            reference.validation_prob,
            compared.validation_prob,
            reference.dataset.meta_validation[HOUSEHOLD_VAR],
            iterations=bootstrap_iterations,
            confidence_level=BASELINE_CONFIDENCE_LEVEL,
            random_state=BASELINE_RANDOM_STATE,
        )
    return comparisons


def recommend_train_set(comparisons: dict[str, list[PairedDifference]]) -> KnhanesTrainSet:
    """
    Train A가 Train B보다 유의하게 나을 때만 Train A를 권장합니다.
    차이가 없으면 측정 체계가 같아 전환식이 필요 없는 Train B가 더 단순합니다.
    Train A를 쓸 때는 중성지방 전환이 유의하게 나을 때만 전환 구성을 권장합니다.
    """
    train_a_is_better = any(
        diff.is_significant and diff.difference > 0 for diff in comparisons[str(KnhanesTrainSet.TRAIN_B)]
    )
    if not train_a_is_better:
        return KnhanesTrainSet.TRAIN_B

    triglyceride_is_better = any(
        diff.is_significant and diff.difference < 0 for diff in comparisons[str(KnhanesTrainSet.TRAIN_A_TG)]
    )
    return KnhanesTrainSet.TRAIN_A_TG if triglyceride_is_better else KnhanesTrainSet.TRAIN_A


def run_knhanes_baseline(
    split_data_dir: Path = SPLIT_DATA_DIR,
    labeled_data_dir: Path = LABELED_DATA_DIR,
    report_dir: Path = BASELINE_REPORT_DIR,
    model_dir: Path = BASELINE_MODEL_DIR,
    algorithms: list[ModelAlgorithm] = BASELINE_ALGORITHMS,
    resampling_options: list[bool] = BASELINE_RESAMPLING_OPTIONS,
    bootstrap_iterations: int = BASELINE_BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """
    질환, 학습 구성, 알고리즘, 재샘플링의 조합을 학습하고 Validation으로 비교합니다.

    1. 모든 조합 학습과 평가
    2. 질환별로 Validation PR-AUC가 가장 높은 알고리즘 선택
    3. 선택한 알고리즘의 학습 구성을 가구 단위 부트스트랩으로 비교
    4. 권장 구성의 모델, 평가 산출물, 보고서 저장
    """
    results: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    report_dir.mkdir(parents=True, exist_ok=True)

    for model_type in ModelType:
        runs: dict[BaselineExperiment, BaselineRun] = {}
        diagnosed: pd.Series | None = None
        for train_set in [BASELINE_REFERENCE_TRAIN_SET, *BASELINE_COMPARED_TRAIN_SETS]:
            dataset = load_baseline_dataset(split_data_dir, model_type, train_set)
            if diagnosed is None:
                diagnosed = load_diagnosed_flags(labeled_data_dir, model_type, dataset.meta_validation[ID_VAR])

            for algorithm in algorithms:
                for use_resampling in resampling_options:
                    experiment = BaselineExperiment(model_type, train_set, algorithm, use_resampling)
                    run = train_baseline(experiment, dataset)
                    runs[experiment] = run
                    results.extend(evaluate_baseline(run, diagnosed))
                    logger.info("Finished %s in %.1fs", experiment, run.seconds)

        summaries[str(model_type)] = _summarize_model(
            model_type, runs, results, report_dir, model_dir, bootstrap_iterations
        )

    report = {
        "evaluated_split": "validation",
        "test_split_used": False,
        "bootstrap_iterations": bootstrap_iterations,
        "models": summaries,
    }
    _save_report(report, results, report_dir)
    return report


def _summarize_model(
    model_type: ModelType,
    runs: dict[BaselineExperiment, BaselineRun],
    results: list[dict[str, Any]],
    report_dir: Path,
    model_dir: Path,
    bootstrap_iterations: int,
) -> dict[str, Any]:
    overall = pd.DataFrame(results)
    overall = overall[overall["model_type"].eq(str(model_type)) & overall["group"].eq("all")]
    best = overall.iloc[int(overall["pr_auc"].to_numpy().argmax())]
    algorithm = ModelAlgorithm(best["algorithm"])
    use_resampling = bool(best["use_resampling"])

    runs_by_train_set = {
        experiment.train_set: run
        for experiment, run in runs.items()
        if experiment.algorithm == algorithm and experiment.use_resampling == use_resampling
    }
    comparisons = compare_train_sets(runs_by_train_set, bootstrap_iterations)
    recommended_train_set = recommend_train_set(comparisons)
    recommended_run = runs_by_train_set[recommended_train_set]

    saved_model_path = model_dir / f"{model_type}_{recommended_train_set}_{algorithm}.pkl"
    recommended_run.bundle.save(saved_model_path)
    ModelEvaluator.from_bundle(
        recommended_run.bundle,
        recommended_run.dataset.X_validation,
        recommended_run.dataset.y_validation,
        report_dir / model_type,
    ).run()

    return {
        "best_algorithm": str(algorithm),
        "best_use_resampling": use_resampling,
        "best_train_set_by_validation": str(best["train_set"]),
        "recommended_train_set": str(recommended_train_set),
        "train_set_comparisons": {
            train_set: [{**asdict(diff), "is_significant": diff.is_significant} for diff in differences]
            for train_set, differences in comparisons.items()
        },
        "saved_model_path": str(saved_model_path),
    }


def _save_report(report: dict[str, Any], results: list[dict[str, Any]], report_dir: Path) -> None:
    results_df = pd.DataFrame(results)
    results_df.to_csv(report_dir / "baseline_results.csv", index=False, encoding="utf-8-sig")
    (report_dir / "baseline_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "baseline_report.md").write_text(render_baseline_report(report, results_df), encoding="utf-8")
    logger.info("Saved baseline report to %s", report_dir)


def render_baseline_report(report: dict[str, Any], results_df: pd.DataFrame) -> str:
    lines = [
        "# KNHANES Baseline 성능 비교 보고서",
        "",
        "- **평가 데이터:** Validation (2022~2023년). Test는 사용하지 않았습니다.",
        "- **모델:** 기본 파라미터. 튜닝과 Calibration 전 결과입니다.",
        "- **선택 기준:** 전체 Validation의 PR-AUC",
        f"- **신뢰구간:** 가구 단위 부트스트랩 {report['bootstrap_iterations']}회, 95%",
    ]
    for model_type, summary in report["models"].items():
        model_rows = results_df[results_df["model_type"].eq(model_type)]
        resampling = "SMOTE" if summary["best_use_resampling"] else "재샘플링 없음"
        lines += [
            "",
            f"## {model_type}",
            "",
            f"- **최고 알고리즘:** {summary['best_algorithm']} ({resampling})",
            f"- **권장 학습 구성:** {summary['recommended_train_set']}",
            "",
            "### 전체 Validation 상위 10개",
            "",
            "| 학습 구성 | 알고리즘 | 재샘플링 | ROC-AUC | PR-AUC | Brier | 평균 예측 |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
        top_rows = model_rows[model_rows["group"].eq("all")].nlargest(10, "pr_auc")
        for row in top_rows.itertuples():
            lines.append(
                f"| {row.train_set} | {row.algorithm} | {'SMOTE' if row.use_resampling else '-'} "
                f"| {row.roc_auc:.3f} | {row.pr_auc:.3f} | {row.brier:.3f} | {row.mean_predicted:.3f} |"
            )

        lines += [
            "",
            "### 학습 구성 비교 (train_a - 비교 구성)",
            "",
            "| 비교 구성 | 지표 | train_a | 비교 구성 값 | 차이 | 95% 신뢰구간 |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for train_set, differences in summary["train_set_comparisons"].items():
            for diff in differences:
                lines.append(
                    f"| {train_set} | {diff['metric']} | {diff['reference']:.3f} | {diff['compared']:.3f} "
                    f"| {diff['difference']:+.3f} | {diff['ci_lower']:+.3f} ~ {diff['ci_upper']:+.3f} |"
                )

        best_rows = model_rows[
            model_rows["train_set"].eq(summary["recommended_train_set"])
            & model_rows["algorithm"].eq(summary["best_algorithm"])
            & model_rows["use_resampling"].eq(summary["best_use_resampling"])
        ]
        lines += [
            "",
            "### 권장 구성의 집단별 성능",
            "",
            "| 집단 | 행 수 | 양성률 | ROC-AUC | PR-AUC | 가중 ROC-AUC | 평균 예측 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for row in best_rows.itertuples():
            lines.append(
                f"| {row.group} | {row.rows} | {row.positive_rate:.3f} | {row.roc_auc:.3f} | {row.pr_auc:.3f} "
                f"| {row.weighted_roc_auc:.3f} | {row.mean_predicted:.3f} |"
            )
    return "\n".join(lines) + "\n"


def _predict_probability(bundle: ModelBundle, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(bundle.model.predict_proba(bundle.transform(X)))[:, 1]


def _read_split_file(split_dir: Path, name: str) -> pd.DataFrame:
    path = split_dir / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"KNHANES split file not found: {path}")
    return pd.read_parquet(path)


if __name__ == "__main__":
    run_knhanes_baseline()
