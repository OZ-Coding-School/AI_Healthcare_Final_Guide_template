from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE, SMOTENC
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from core import settings
from src.enums import ModelAlgorithm

ModelEstimator: TypeAlias = (
    LGBMClassifier | XGBClassifier | RandomForestClassifier | GradientBoostingClassifier | LogisticRegression
)
ModelType: TypeAlias = ModelEstimator


@dataclass
class ModelBundle:
    model: ModelEstimator
    preprocessor: ColumnTransformer
    post_preprocessor: ColumnTransformer | None
    feature_names: list[str]
    threshold: float = 0.5
    feature_metadata: list[Any] | None = None
    # 원 모델과 분리해 저장해야 SHAP TreeExplainer가 원 모델에 바로 접근할 수 있습니다.
    calibrator: Any | None = None
    risk_thresholds: dict[str, float] | None = None

    def calibrate(self, raw_prob: np.ndarray) -> np.ndarray:
        """모델의 양성 확률에 보정기를 적용합니다. 보정기가 없으면 그대로 반환합니다."""
        raw_prob = np.asarray(raw_prob, dtype=float)
        if self.calibrator is None:
            return raw_prob
        return np.asarray(self.calibrator.transform(raw_prob), dtype=float)

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """원본 입력을 전처리하고 보정까지 적용한 양성 확률(1차원)을 반환합니다."""
        raw_prob = np.asarray(self.model.predict_proba(self.transform(X)))[:, 1]
        return self.calibrate(raw_prob)

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """입력 데이터를 모델 학습에 사용된 전처리 파이프라인을 거쳐 2D NumPy 배열로 변환합니다."""
        x_proc: Any = self.preprocessor.transform(X) if self.preprocessor is not None else X
        if self.post_preprocessor is not None:
            x_proc = self.post_preprocessor.transform(x_proc)
        if hasattr(x_proc, "toarray"):
            x_proc = x_proc.toarray()
        return np.asarray(x_proc)

    def save(self, filepath: Path | str) -> None:
        save_path = Path(filepath)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "preprocessor": self.preprocessor,
                "post_preprocessor": self.post_preprocessor,
                "feature_names": self.feature_names,
                "threshold": self.threshold,
                "feature_metadata": self.feature_metadata,
                "calibrator": self.calibrator,
                "risk_thresholds": self.risk_thresholds,
            },
            save_path,
        )

    @classmethod
    def load(cls, filepath: Path | str) -> "ModelBundle":
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        bundle = joblib.load(path)
        if isinstance(bundle, cls):
            return bundle
        if isinstance(bundle, dict):
            return cls(
                model=bundle["model"],
                preprocessor=bundle["preprocessor"],
                post_preprocessor=bundle.get("post_preprocessor", None),
                feature_names=bundle["feature_names"],
                threshold=bundle.get("threshold", 0.5),
                feature_metadata=bundle.get("feature_metadata", None),
                calibrator=bundle.get("calibrator", None),
                risk_thresholds=bundle.get("risk_thresholds", None),
            )
        raise TypeError(f"Loaded object is not a ModelBundle or dict: {type(bundle)}")


class ModelFactory:
    """
    알고리즘 및 하이퍼파라미터 설정에 따라 모델 인스턴스를 생성하는 팩토리 클래스
    """

    @staticmethod
    def create(
        algorithm: ModelAlgorithm,
        random_state: int = 42,
        hyperparameters: dict[str, Any] | None = None,
    ) -> ModelEstimator:
        params: dict[str, Any] = hyperparameters.copy() if hyperparameters is not None else {}

        match algorithm:
            case ModelAlgorithm.RANDOM_FOREST:
                params.setdefault("n_estimators", 100)
                params.setdefault("random_state", random_state)
                return RandomForestClassifier(**params)
            case ModelAlgorithm.XGBOOST:
                params.setdefault("n_estimators", 100)
                params.setdefault("random_state", random_state)
                return XGBClassifier(**params)
            case ModelAlgorithm.LOGISTIC_REGRESSION:
                params.setdefault("random_state", random_state)
                return LogisticRegression(**params)
            case ModelAlgorithm.LIGHTGBM:
                params.setdefault("n_estimators", 100)
                params.setdefault("random_state", random_state)
                return LGBMClassifier(**params)
            case ModelAlgorithm.GRADIENT_BOOSTING:
                params.setdefault("n_estimators", 100)
                params.setdefault("random_state", random_state)
                return GradientBoostingClassifier(**params)
            case _:
                raise ValueError(f"Invalid algorithm: {algorithm}")


class BinaryClassificationModelTrainer:
    def __init__(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        output_filename: str | None = None,
        *,
        output_dir: Path | None = None,
        model_dir: Path | None = None,
        algorithm: ModelAlgorithm,
        use_resampling: bool = False,
        random_state: int = 42,
        hyperparameters: dict[str, Any] | None = None,
        threshold: float = 0.5,
    ) -> None:
        self.x_train = x_train
        self.y_train = y_train
        self.algorithm = algorithm
        self.hyperparameters = hyperparameters
        self.use_resampling = use_resampling
        self.random_state = random_state
        self.output_dir = output_dir or model_dir or settings.MODEL_DIR
        self.output_filename = output_filename
        self.threshold = threshold

    def _get_pre_resampling_preprocessor(
        self,
        numeric_features: list[str] | None = None,
        categorical_features: list[str] | None = None,
    ) -> ColumnTransformer:
        transformers = []
        if numeric_features:
            transformers.append(("num", self._get_numeric_transformer(), numeric_features))
        if categorical_features:
            transformers.append(("cat", self._get_categorical_transformer(), categorical_features))

        return ColumnTransformer(transformers=transformers, verbose_feature_names_out=False)

    def _get_post_resampling_preprocessor(
        self, numeric_features: list[str], categorical_features: list[str]
    ) -> ColumnTransformer:
        transformers = []
        if numeric_features:
            transformers.append(("num", "passthrough", numeric_features))
        if categorical_features:
            transformers.append(
                ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features)
            )

        return ColumnTransformer(transformers=transformers, verbose_feature_names_out=False)

    def train(self, auto_save: bool = False) -> ModelBundle:
        numeric_features = self.x_train.select_dtypes(include=["number"]).columns.tolist()
        categorical_features = self.x_train.select_dtypes(include=["object", "string", "category"]).columns.tolist()

        preprocessor = self._get_pre_resampling_preprocessor(numeric_features, categorical_features)
        preprocessor.set_output(transform="pandas")

        x_train_proc = preprocessor.fit_transform(self.x_train)
        y_train = self.y_train.copy()

        # Resampling 여부에 따라 전처리 수행
        post_preprocessor = None
        if self.use_resampling:
            if categorical_features:
                x_train_proc, y_train = self._apply_smotenc(x_train_proc, self.y_train, categorical_features)
                post_preprocessor = self._get_post_resampling_preprocessor(numeric_features, categorical_features)
                x_train_proc = post_preprocessor.fit_transform(x_train_proc)
            else:
                x_train_proc, y_train = self._apply_smote(x_train_proc, self.y_train)

        # 선택된 알고리즘에 따라 모델 생성 및 학습
        model = ModelFactory.create(
            algorithm=self.algorithm,
            random_state=self.random_state,
            hyperparameters=self.hyperparameters,
        )
        model.fit(x_train_proc, y_train)

        feature_names = (
            self._extract_feature_names(post_preprocessor)
            if post_preprocessor is not None
            else self._extract_feature_names(preprocessor)
        )

        feature_metadata = self._build_feature_metadata(feature_names)

        model_bundle = ModelBundle(
            model=model,
            preprocessor=preprocessor,
            post_preprocessor=post_preprocessor,
            feature_names=feature_names,
            threshold=self.threshold,
            feature_metadata=feature_metadata,
        )

        if auto_save:
            self.save(model_bundle)

        return model_bundle

    def _build_feature_metadata(self, feature_names: list[str]) -> list[dict[str, str]]:
        metadata: list[dict[str, str]] = []
        original_cols = self.x_train.columns.tolist()
        for f_name in feature_names:
            matched_orig = f_name
            if f_name in original_cols:
                matched_orig = f_name
            else:
                for orig in original_cols:
                    if f_name.startswith(f"{orig}_") or f_name.startswith(f"cat__{orig}_") or f_name == f"num__{orig}":
                        matched_orig = orig
                        break
            metadata.append(
                {
                    "model_feature_name": f_name,
                    "original_feature_name": matched_orig,
                    "display_name": matched_orig,
                }
            )
        return metadata

    def save(
        self,
        model_bundle: ModelBundle,
        output_filename: str | None = None,
        filepath: Path | None = None,
    ) -> Path:
        if filepath is not None:
            save_path = filepath
        else:
            filename_base = output_filename if output_filename is not None else self.output_filename
            if filename_base is None:
                raise ValueError("output_filename or filepath must be specified for model saving.")
            filename = f"{filename_base}_{self.algorithm}"
            if self.use_resampling:
                filename += "_resampled"
            save_path = self.output_dir / f"{filename}.pkl"

        model_bundle.save(save_path)
        return save_path

    def _extract_feature_names(self, preprocessor: ColumnTransformer) -> list[str]:
        if hasattr(preprocessor, "get_feature_names_out"):
            return preprocessor.get_feature_names_out().tolist()
        return self.x_train.columns.tolist()

    def _get_numeric_transformer(self) -> Pipeline:
        steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]

        if self.algorithm == ModelAlgorithm.LOGISTIC_REGRESSION or self.use_resampling:
            steps.append(("scaler", StandardScaler()))
        return Pipeline(steps=steps)

    def _get_categorical_transformer(self) -> Pipeline:
        steps: list[tuple[str, Any]] = [
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ]

        if not self.use_resampling:
            steps.append(("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)))

        return Pipeline(steps=steps)

    def _apply_smotenc(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        categorical_features: list[str],
    ) -> tuple[pd.DataFrame, pd.Series]:
        categorical_indices = [x_train.columns.get_loc(col) for col in categorical_features]
        min_class_count = y_train.value_counts().min()
        k_neighbors = min(5, max(1, min_class_count - 1))
        smote = SMOTENC(
            categorical_features=categorical_indices,
            k_neighbors=k_neighbors,
            random_state=self.random_state,
        )
        x_resampled, y_resampled = smote.fit_resample(
            x_train,
            y_train,
        )
        if not isinstance(x_resampled, pd.DataFrame):
            x_resampled = pd.DataFrame(x_resampled, columns=x_train.columns)
            for col in x_train.columns:
                x_resampled[col] = x_resampled[col].astype(x_train[col].dtype)
        if not isinstance(y_resampled, pd.Series):
            y_resampled = pd.Series(y_resampled, name=y_train.name)
        return x_resampled, y_resampled

    def _apply_smote(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> tuple[pd.DataFrame, pd.Series]:
        min_class_count = y_train.value_counts().min()
        k_neighbors = min(5, max(1, min_class_count - 1))
        smote = SMOTE(k_neighbors=k_neighbors, random_state=self.random_state)
        x_resampled, y_resampled = smote.fit_resample(
            x_train,
            y_train,
        )
        if not isinstance(x_resampled, pd.DataFrame):
            x_resampled = pd.DataFrame(x_resampled, columns=x_train.columns)
            for col in x_train.columns:
                x_resampled[col] = x_resampled[col].astype(x_train[col].dtype)
        if not isinstance(y_resampled, pd.Series):
            y_resampled = pd.Series(y_resampled, name=y_train.name)
        return x_resampled, y_resampled
