from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from src.components.knhanes_multi_year_loader import YEAR_VAR, KnhanesDataValidationError
from src.enums import KnhanesTrainSet
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.knhanes_preprocessing_configs import TRAINING_META_VARS
from src.knhanes_split_configs import (
    KNHANES_DEVELOPMENT_YEARS,
    KNHANES_EARLY_TRAIN_YEARS,
    KNHANES_EARLY_YEAR_TRAIN_SETS,
    KNHANES_SPLIT_RANDOM_STATE,
    KNHANES_TEST_YEARS,
    KNHANES_VALIDATION_FOLDS,
)

ID_VAR = "ID"
HOUSEHOLD_VAR = "ID_fam"

EARLY_TRAIN_GROUP = "early_train"
TRAIN_GROUP = "train"
VALIDATION_GROUP = "validation"
TEST_GROUP = "test"


@dataclass
class SplitData:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series


@dataclass
class KnhanesSplitData(SplitData):
    meta_train: pd.DataFrame
    meta_validation: pd.DataFrame
    meta_test: pd.DataFrame


class DataSplitter:
    """
    데이터셋을 주어진 비율로 학습, 검증, 테스트 세트로 분리하고 저장하는 유틸리티 클래스.

    이 클래스는 데이터프레임을 분할하여 데이터 분석 및 모델 학습에 필요한 다양한
    데이터 세트를 생성하는 데 사용됩니다. 분할 비율은 사용자가 지정할 수 있으며,
    분할된 데이터는 Parquet 파일 형식으로 저장됩니다.
    """

    def __init__(
        self,
        output_dir: Path | str,
        train_size: float = 0.6,
        test_size: float = 0.2,
        val_size: float = 0.2,
        random_state: int = 42,
    ) -> None:
        self.train_size = train_size
        self.test_size = test_size
        self.val_size = val_size
        self.random_state = random_state
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._validate_split_ratio()

    def _validate_split_ratio(self) -> None:
        """
        분할 비율이 유효한지 확인하는 메서드.
        """
        total = self.train_size + self.val_size + self.test_size
        if not 0 < self.train_size < 1:
            raise ValueError("train_size must be between 0 and 1")
        if not 0 <= self.val_size < 1:
            raise ValueError("val_size must be between 0 and 1")
        if not 0 < self.test_size < 1:
            raise ValueError("test_size must be between 0 and 1")
        if not abs(total - 1.0) < 1e-9:
            raise ValueError("train_size + val_size + test_size must equal 1.0")

    def split(self, processed_df: pd.DataFrame, target_var: str) -> SplitData:
        """
        주어진 DataFrame을 학습(train), 검증(validation), 테스트(test) 데이터셋으로 분할합니다.
        특히 target 변수를 기준으로 stratified split을 수행하여 데이터가 균등하게 분리되도록 보장합니다.

        :param processed_df: 데이터 분리를 위한 전처리된 pandas DataFrame
        :type processed_df: pandas.DataFrame
        :param target_var: 분할 시 기준이 되는 종속 변수의 이름
        :type target_var: str
        :return: train, validation, test 데이터가 X(특징)와 y(target 변수)로 나누어져 있는 SplitData 객체
        :rtype: SplitData

        :raises ValueError: target variable이 DataFrame의 열 이름에 존재하지 않을 경우 발생
        """
        if target_var not in processed_df.columns:
            raise ValueError(f"Target variable '{target_var}' not found")

        # 2-way split (Train / Test only)
        if self.val_size == 0.0:
            train, test = train_test_split(
                processed_df,
                test_size=self.test_size,
                stratify=processed_df[target_var],
                random_state=self.random_state,
            )
            X_train, y_train = self._split_features_target(train, target_var)
            X_test, y_test = self._split_features_target(test, target_var)
            X_validation = pd.DataFrame(columns=X_train.columns)
            y_validation = pd.Series(dtype=y_train.dtype, name=y_train.name)

            return SplitData(
                X_train=X_train,
                y_train=y_train,
                X_validation=X_validation,
                y_validation=y_validation,
                X_test=X_test,
                y_test=y_test,
            )

        # 1. Test 분리
        train, temp = train_test_split(
            processed_df,
            test_size=self.val_size + self.test_size,
            stratify=processed_df[target_var],
            random_state=self.random_state,
        )

        # 2. Validation 비율을 remaining 데이터 기준으로 변환
        test_ratio = self.test_size / (self.val_size + self.test_size)

        # 3. Train / Validation 분리
        validation, test = train_test_split(
            temp,
            test_size=test_ratio,
            stratify=temp[target_var],
            random_state=self.random_state,
        )

        # 4. X / y 분리
        X_train, y_train = self._split_features_target(train, target_var)
        X_validation, y_validation = self._split_features_target(validation, target_var)
        X_test, y_test = self._split_features_target(test, target_var)

        return SplitData(
            X_train=X_train,
            y_train=y_train,
            X_validation=X_validation,
            y_validation=y_validation,
            X_test=X_test,
            y_test=y_test,
        )

    def save_to_parquet(
        self, split_data: SplitData, compression: Literal["snappy", "gzip", "brotli", "lz4", "zstd"] = "snappy"
    ) -> None:
        """
        주어진 데이터를 Parquet 형식으로 변환하여 저장합니다.

        이 메서드는 데이터셋을 Parquet 파일로 저장합니다. 데이터는 SplitData 형식으로 제공되며,
        이 형식은 데이터를 저장할 파일 이름과 데이터를 매핑하는 구조를 가집니다. 기본적으로
        압축 방식으로 "snappy"를 사용하며, 다른 압축 방식을 지정할 수도 있습니다.

        :param split_data: Parquet 파일로 저장할 데이터를 포함하는 SplitData 객체
        :type split_data: SplitData
        :param compression: Parquet 파일이 압축될 방식. 선택 가능한 값은 "snappy", "gzip",
            "brotli", "lz4", "zstd"입니다. 기본값은 "snappy"입니다.
        :type compression: Literal["snappy", "gzip", "brotli", "lz4", "zstd"]
        :return: 없음. 데이터를 저장하는 작업만 수행합니다.
        :rtype: None
        """
        for name, data in vars(split_data).items():
            if isinstance(data, pd.Series):
                data = data.to_frame() if data.name is not None else data.to_frame(name=name)

            data.to_parquet(self.output_dir / f"{name}.parquet", index=False, compression=compression)

    @staticmethod
    def _split_features_target(df: pd.DataFrame, target_var: str) -> tuple[pd.DataFrame, pd.Series]:
        """
        DataFrame을 Feature(X)와 Target(y)로 분리합니다.
        """
        X = df.drop(columns=[target_var])
        y = df[target_var]

        return X, y


class KnhanesYearGroupSplitter:
    def __init__(
        self,
        validation_folds: int = KNHANES_VALIDATION_FOLDS,
        random_state: int = KNHANES_SPLIT_RANDOM_STATE,
    ) -> None:
        if validation_folds < 2:
            raise ValueError("validation_folds must be at least 2")
        self.validation_folds = validation_folds
        self.random_state = random_state

    def assign_groups(self, df: pd.DataFrame) -> pd.Series:
        """
        행마다 분할 그룹을 정합니다. 전환 전 데이터로 한 번만 정해 학습 구성이 같은 Validation과 Test를 쓰게 합니다.

        - 2020~2021년: early_train
        - 2022~2023년: 같은 가구가 나뉘지 않도록 train과 validation으로 분할
        - 2024년: test
        """
        self._validate_input(df)

        groups = pd.Series(TEST_GROUP, index=df.index, name="split_group", dtype="object")
        groups[df[YEAR_VAR].isin(KNHANES_EARLY_TRAIN_YEARS)] = EARLY_TRAIN_GROUP

        development_df = df[df[YEAR_VAR].isin(KNHANES_DEVELOPMENT_YEARS)].sort_values(ID_VAR)
        fold_splitter = StratifiedGroupKFold(
            n_splits=self.validation_folds,
            shuffle=True,
            random_state=self.random_state,
        )
        train_positions, validation_positions = next(
            fold_splitter.split(development_df, development_df[DISEASE_LABEL_VAR], development_df[HOUSEHOLD_VAR])
        )
        groups[development_df.index[train_positions]] = TRAIN_GROUP
        groups[development_df.index[validation_positions]] = VALIDATION_GROUP

        self._validate_groups(df, groups)
        return groups

    def split(self, df: pd.DataFrame, groups: pd.Series, train_set: KnhanesTrainSet) -> KnhanesSplitData:
        """
        분할 그룹에 따라 학습 구성의 X, y, 메타 데이터를 만듭니다.
        메타 변수는 연도별 성능 확인과 가중 평가에만 쓰도록 X에서 분리합니다.
        """
        train_groups = [TRAIN_GROUP]
        if train_set in KNHANES_EARLY_YEAR_TRAIN_SETS:
            train_groups.append(EARLY_TRAIN_GROUP)

        X_train, y_train, meta_train = self._split_columns(df[groups.isin(train_groups)])
        X_validation, y_validation, meta_validation = self._split_columns(df[groups.eq(VALIDATION_GROUP)])
        X_test, y_test, meta_test = self._split_columns(df[groups.eq(TEST_GROUP)])

        return KnhanesSplitData(
            X_train=X_train,
            y_train=y_train,
            X_validation=X_validation,
            y_validation=y_validation,
            X_test=X_test,
            y_test=y_test,
            meta_train=meta_train,
            meta_validation=meta_validation,
            meta_test=meta_test,
        )

    @staticmethod
    def summarize(split_data: KnhanesSplitData) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        for name in ["train", "validation", "test"]:
            labels: pd.Series = getattr(split_data, f"y_{name}")
            meta: pd.DataFrame = getattr(split_data, f"meta_{name}")
            summary[name] = {
                "rows": len(labels),
                "households": int(meta[HOUSEHOLD_VAR].nunique()),
                "positive": int(labels.sum()),
                "positive_rate": round(float(labels.mean()), 4),
                "years": sorted(int(year) for year in meta[YEAR_VAR].unique()),
            }
        return summary

    @staticmethod
    def _split_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        return (
            df.drop(columns=[*TRAINING_META_VARS, DISEASE_LABEL_VAR]).reset_index(drop=True),
            df[DISEASE_LABEL_VAR].reset_index(drop=True),
            df[TRAINING_META_VARS].reset_index(drop=True),
        )

    def _validate_input(self, df: pd.DataFrame) -> None:
        required_vars = [*TRAINING_META_VARS, DISEASE_LABEL_VAR]
        missing_vars = [var_name for var_name in required_vars if var_name not in df.columns]
        if missing_vars:
            raise KnhanesDataValidationError(f"Missing split columns: {missing_vars}")

        split_vars = [ID_VAR, HOUSEHOLD_VAR, YEAR_VAR, DISEASE_LABEL_VAR]
        columns_with_missing = [var_name for var_name in split_vars if df[var_name].isna().any()]
        if columns_with_missing:
            raise KnhanesDataValidationError(f"Split columns have missing values: {columns_with_missing}")

        if df[ID_VAR].duplicated().any():
            raise KnhanesDataValidationError(f"{ID_VAR} must be unique")

        expected_years = {*KNHANES_EARLY_TRAIN_YEARS, *KNHANES_DEVELOPMENT_YEARS, *KNHANES_TEST_YEARS}
        actual_years = set(df[YEAR_VAR].unique())
        if actual_years != expected_years:
            raise KnhanesDataValidationError(
                f"Split years must be {sorted(expected_years)}, got {sorted(actual_years)}"
            )

    @staticmethod
    def _validate_groups(df: pd.DataFrame, groups: pd.Series) -> None:
        """
        같은 가구가 여러 그룹에 있으면 가족 간 유사성이 평가 데이터로 새어 나갑니다.
        """
        group_counts = groups.groupby(df[HOUSEHOLD_VAR]).nunique()
        if group_counts.gt(1).any():
            raise KnhanesDataValidationError(f"Households across split groups: {int(group_counts.gt(1).sum())}")
