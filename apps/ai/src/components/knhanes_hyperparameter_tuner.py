"""
가구 단위 교차검증으로 하이퍼파라미터를 튜닝합니다.

- 폴드는 ID_fam 기준으로 나눠 같은 가구가 학습과 검증에 함께 들어가지 않습니다.
- 폴드마다 Trainer로 전처리부터 다시 fit하므로 폴드 밖 정보가 전처리에 섞이지 않습니다.
- Validation과 Test는 이 모듈에서 다루지 않습니다.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import average_precision_score, log_loss
from sklearn.model_selection import StratifiedGroupKFold

from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.components.model_trainer import BinaryClassificationModelTrainer
from src.enums import ModelAlgorithm
from src.knhanes_tuning_configs import CategoricalParam, FloatParam, IntParam, SearchParam

optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass(frozen=True)
class CrossValidationScore:
    pr_auc: float
    log_loss: float
    fold_pr_aucs: list[float]


@dataclass(frozen=True)
class TuningResult:
    algorithm: ModelAlgorithm
    best_params: dict[str, Any]
    best_score: CrossValidationScore
    completed_trials: int
    trials: pd.DataFrame


def make_household_folds(
    y: pd.Series, households: pd.Series, n_folds: int, random_state: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """양성 비율을 맞추면서 가구 단위로 폴드를 나눕니다. 같은 가구는 한 폴드에만 들어갑니다."""
    if len(y) != len(households):
        raise KnhanesDataValidationError("y and households must have the same length")
    if households.isna().any():
        raise KnhanesDataValidationError("households must not contain missing values")
    if not y.isin([0, 1]).all() or y.nunique() != 2:
        raise KnhanesDataValidationError("y must contain both 0 and 1 only")
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")
    if households.nunique() < n_folds:
        raise KnhanesDataValidationError("Not enough households for the requested folds")

    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    folds = [
        (train_idx, validation_idx)
        for train_idx, validation_idx in splitter.split(np.zeros(len(y)), y.to_numpy(), households.to_numpy())
    ]
    for _, validation_idx in folds:
        if y.iloc[validation_idx].nunique() != 2:
            raise KnhanesDataValidationError("Every fold must contain both classes")
    return folds


def cross_validate_oof(
    X: pd.DataFrame,
    y: pd.Series,
    folds: list[tuple[np.ndarray, np.ndarray]],
    algorithm: ModelAlgorithm,
    hyperparameters: dict[str, Any],
    random_state: int,
    n_jobs: int = 1,
) -> np.ndarray:
    """폴드별로 학습해 Train 전체의 OOF(Out-Of-Fold) 양성 확률을 반환합니다."""
    if len(X) != len(y):
        raise KnhanesDataValidationError("X and y must have the same length")

    fold_probs = Parallel(n_jobs=n_jobs)(
        delayed(_fit_predict_fold)(X, y, train_idx, validation_idx, algorithm, hyperparameters, random_state)
        for train_idx, validation_idx in folds
    )

    oof_prob = np.full(len(y), np.nan)
    for (_, validation_idx), prob in zip(folds, fold_probs, strict=True):
        oof_prob[validation_idx] = prob
    if np.isnan(oof_prob).any():
        raise KnhanesDataValidationError("Folds must cover every training row exactly once")
    return oof_prob


def score_oof(y: pd.Series, oof_prob: np.ndarray, folds: list[tuple[np.ndarray, np.ndarray]]) -> CrossValidationScore:
    """폴드별 PR-AUC의 평균과 전체 OOF Log loss를 계산합니다."""
    labels = y.to_numpy()
    fold_pr_aucs = [
        float(average_precision_score(labels[validation_idx], oof_prob[validation_idx])) for _, validation_idx in folds
    ]
    return CrossValidationScore(
        pr_auc=float(np.mean(fold_pr_aucs)),
        log_loss=float(log_loss(labels, oof_prob, labels=[0, 1])),
        fold_pr_aucs=fold_pr_aucs,
    )


class KnhanesHyperparameterTuner:
    """
    Optuna(TPE)로 탐색 공간을 찾고 가구 단위 CV PR-AUC가 가장 높은 파라미터를 고릅니다.
    PR-AUC 차이가 허용 범위 안이면 Log loss가 낮은 파라미터를 고릅니다.
    """

    def __init__(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        folds: list[tuple[np.ndarray, np.ndarray]],
        algorithm: ModelAlgorithm,
        search_space: dict[str, SearchParam],
        fixed_hyperparameters: dict[str, Any],
        *,
        random_state: int,
        pr_auc_tie_tolerance: float,
        n_jobs: int = 1,
    ) -> None:
        if not search_space:
            raise ValueError(f"{algorithm}: search space must not be empty")
        overlap = set(search_space) & set(fixed_hyperparameters)
        if overlap:
            raise ValueError(f"{algorithm}: parameters are both searched and fixed: {sorted(overlap)}")
        if pr_auc_tie_tolerance < 0:
            raise ValueError("pr_auc_tie_tolerance must not be negative")

        self.X = X
        self.y = y
        self.folds = folds
        self.algorithm = algorithm
        self.search_space = search_space
        self.fixed_hyperparameters = fixed_hyperparameters
        self.random_state = random_state
        self.pr_auc_tie_tolerance = pr_auc_tie_tolerance
        self.n_jobs = n_jobs

    def tune(self, n_trials: int, timeout: float | None = None) -> TuningResult:
        if n_trials < 1:
            raise ValueError("n_trials must be at least 1")

        sampler = optuna.samplers.TPESampler(seed=self.random_state)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(self._objective, n_trials=n_trials, timeout=timeout)

        completed = [trial for trial in study.trials if trial.state == optuna.trial.TrialState.COMPLETE]
        if not completed:
            raise RuntimeError(f"{self.algorithm}: no trial completed")

        best_trial = select_best_trial(completed, self.pr_auc_tie_tolerance)
        return TuningResult(
            algorithm=self.algorithm,
            best_params={**self.fixed_hyperparameters, **best_trial.params},
            best_score=CrossValidationScore(
                pr_auc=float(best_trial.value),
                log_loss=float(best_trial.user_attrs["log_loss"]),
                fold_pr_aucs=list(best_trial.user_attrs["fold_pr_aucs"]),
            ),
            completed_trials=len(completed),
            trials=study.trials_dataframe(attrs=("number", "value", "params", "user_attrs", "state", "duration")),
        )

    def _objective(self, trial: optuna.Trial) -> float:
        params = {name: _suggest(trial, name, spec) for name, spec in self.search_space.items()}
        oof_prob = cross_validate_oof(
            self.X,
            self.y,
            self.folds,
            self.algorithm,
            {**self.fixed_hyperparameters, **params},
            self.random_state,
            self.n_jobs,
        )
        score = score_oof(self.y, oof_prob, self.folds)
        trial.set_user_attr("log_loss", score.log_loss)
        trial.set_user_attr("fold_pr_aucs", score.fold_pr_aucs)
        return score.pr_auc


def select_best_trial(trials: list[optuna.trial.FrozenTrial], pr_auc_tie_tolerance: float) -> optuna.trial.FrozenTrial:
    """PR-AUC 최고값과의 차이가 허용 범위 안인 trial 중 Log loss가 가장 낮은 trial을 고릅니다."""
    best_pr_auc = max(float(trial.value) for trial in trials)
    tied = [trial for trial in trials if best_pr_auc - float(trial.value) <= pr_auc_tie_tolerance]
    return min(tied, key=lambda trial: (float(trial.user_attrs["log_loss"]), trial.number))


def _suggest(trial: optuna.Trial, name: str, spec: SearchParam) -> Any:
    match spec:
        case IntParam():
            return trial.suggest_int(name, spec.low, spec.high, log=spec.log)
        case FloatParam():
            return trial.suggest_float(name, spec.low, spec.high, log=spec.log)
        case CategoricalParam():
            return trial.suggest_categorical(name, list(spec.choices))
        case _:
            raise TypeError(f"Unsupported search parameter: {spec!r}")


def _fit_predict_fold(
    X: pd.DataFrame,
    y: pd.Series,
    train_idx: np.ndarray,
    validation_idx: np.ndarray,
    algorithm: ModelAlgorithm,
    hyperparameters: dict[str, Any],
    random_state: int,
) -> np.ndarray:
    bundle = BinaryClassificationModelTrainer(
        x_train=X.iloc[train_idx],
        y_train=y.iloc[train_idx],
        algorithm=algorithm,
        random_state=random_state,
        hyperparameters=hyperparameters,
    ).train()
    return np.asarray(bundle.model.predict_proba(bundle.transform(X.iloc[validation_idx])))[:, 1]
