from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from core import settings
from core.enums import ModelAlgorithm


@dataclass
class ModelBundle:
    model: Any
    preprocessor: ColumnTransformer
    feature_names: list[str]


class BinaryClassificationModelTrainer:
    def __init__(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        output_filename: str,
        *,
        algorithm: ModelAlgorithm,
        use_smote: bool = False,
        random_state: int = 42,
        model_dir: Path = settings.MODEL_DIR,
    ) -> None:
        self.x_train = x_train
        self.y_train = y_train
        self.algorithm = algorithm
        self.use_smote = use_smote
        self.random_state = random_state
        self.model_dir = model_dir
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._numeric_features = self.x_train.select_dtypes(include=["int64", "float64"]).columns.tolist()
        self._categorical_features = self.x_train.select_dtypes(
            include=["object", "string", "category"]
        ).columns.tolist()
        self.output_filename = f"{output_filename}_{self.algorithm}"
        if use_smote:
            self.output_filename += "_smote"

    def train(self) -> ModelBundle:
        # 전처리기(피처 엔지니어링 용도)
        preprocessor = self._get_preprocessor()

        # 피쳐 엔지니어링 적용
        x_train_proc = preprocessor.fit_transform(self.x_train)

        # 클래스 불균형 처리(SMOTE)
        x_train_proc, y_train = self._apply_smote(x_train_proc, self.y_train)

        # 선택된 알고리즘에 따라 학습
        model = self._train_by_algorithm(x_train_proc, y_train)

        # 컬럼명 추출
        cat_encoder = preprocessor.named_transformers_["cat"].named_steps["onehot"]
        cat_cols = cat_encoder.get_feature_names_out(self._categorical_features).tolist()
        all_feature_names = self._numeric_features + cat_cols

        # 모델 저장
        self._save_model(model, preprocessor, all_feature_names)

        return ModelBundle(model, preprocessor, all_feature_names)

    def _get_preprocessor(self) -> ColumnTransformer:
        return ColumnTransformer(
            transformers=[
                ("num", self._get_numeric_transformer(), self._numeric_features),
                ("cat", self._get_categorical_transformer(), self._categorical_features),
            ]
        )

    def _get_numeric_transformer(self) -> Pipeline:
        return Pipeline(steps=[("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])

    def _get_categorical_transformer(self) -> Pipeline:
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )

    def _apply_smote(
        self,
        x_train: np.ndarray,
        y_train: pd.Series,
    ) -> tuple[np.ndarray, pd.Series]:
        if not self.use_smote:
            return x_train, y_train
        smote = SMOTE(random_state=self.random_state)

        return smote.fit_resample(x_train, y_train)

    def _train_by_algorithm(self, x_train_proc: np.ndarray, y_train: pd.Series) -> Any:
        match self.algorithm:
            case ModelAlgorithm.RANDOM_FOREST:
                model = RandomForestClassifier(n_estimators=100, random_state=self.random_state)
                model.fit(x_train_proc, y_train)
            case ModelAlgorithm.XGBOOST:
                model = XGBClassifier(n_estimators=100, random_state=self.random_state)
                model.fit(x_train_proc, y_train)
            case ModelAlgorithm.LOGISTIC_REGRESSION:
                model = LogisticRegression(random_state=self.random_state)
                model.fit(x_train_proc, y_train)
            case ModelAlgorithm.LIGHTGBM:
                model = LGBMClassifier(n_estimators=100, random_state=self.random_state)
                model.fit(x_train_proc, y_train)
            case ModelAlgorithm.GRADIENT_BOOSTING:
                model = GradientBoostingClassifier(n_estimators=100, random_state=self.random_state)
                model.fit(x_train_proc, y_train)
            case _:
                raise ValueError("Invalid algorithm")

        return model

    def _save_model(self, model: Any, preprocessor: ColumnTransformer, all_feature_names: list[str]) -> None:
        model_path = self.model_dir / f"{self.output_filename}.pkl"
        joblib.dump({"model": model, "preprocessor": preprocessor, "feature_names": all_feature_names}, model_path)
