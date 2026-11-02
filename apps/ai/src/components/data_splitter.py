from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from sklearn.model_selection import train_test_split


@dataclass
class SplitData:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series


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
