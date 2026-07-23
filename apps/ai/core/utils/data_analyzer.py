from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from core import settings
from core.utils import DataLoader


class DataAnalyzer:
    def __init__(
        self,
        target_vars: list[str] | None = None,
        data_path: str | Path = settings.DATA_DIR / "raw/knhanes/knhanes.csv",
        output_dir_path: str | Path = settings.DOCS_DIR / "eda_results/knhanes",
    ) -> None:
        if target_vars is None:
            raise ValueError("Target variables must be provided.")

        self.plot_dir = Path(output_dir_path) / "plots"
        self._mkdir_if_not_exists(self.plot_dir)
        self.csv_dir = Path(output_dir_path) / "csv"
        self._mkdir_if_not_exists(self.csv_dir)

        self.target_vars = target_vars
        self.df = self._load_data(data_path)
        self.correlation_df = self._prepare_correlation_df()
        self._correlation_matrix = self.correlation_df.corr(numeric_only=True)
        self.categorical_cols = set(self.df.select_dtypes(include=["object", "category"]).columns)

    @property
    def correlation_matrix(self) -> pd.DataFrame:
        return self._correlation_matrix

    def run(self) -> None:
        # 전체 변수 요약
        self.save_summary_statistics_to_csv()

        # 결측치 분석
        self.save_missing_value_plot()
        self.save_missing_value_summary_to_csv()

        # 변수 분포 분석
        self.save_target_distribution()
        self.save_feature_distribution()

        # 상관관계 분석
        self.save_correlation_matrix()
        self.save_top_feature_plots()
        self.save_correlation_values_to_csv()

    def _mkdir_if_not_exists(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_data(data_path: str | Path) -> pd.DataFrame:
        df = DataLoader().load(data_path).df
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Expected pandas DataFrame")
        if df.empty:
            raise ValueError("DataFrame is empty")
        return df

    def _prepare_correlation_df(self) -> pd.DataFrame:
        """
        상관관계 분석을 위한 DataFrame을 생성합니다.
        범주형 변수는 category code로 변환하며,
        원본 DataFrame은 변경하지 않습니다.
        """
        df_corr = self.df.copy()
        categorical_cols = df_corr.select_dtypes(include=["object", "category"]).columns

        for col in categorical_cols:
            df_corr[col] = df_corr[col].astype("category").cat.codes

        return df_corr

    def _save_plot(self, filename: str) -> None:
        plt.tight_layout()
        plt.savefig(self.plot_dir / filename, dpi=300, bbox_inches="tight")
        plt.close()

    def save_target_distribution(self) -> None:
        """
        타겟 변수의 분포를 시각화하여 파일로 저장합니다.
        지정된 출력 디렉토리에 타겟 변수의 분포를 나타내는 시각화 이미지를 생성하고 저장합니다.
        """
        n_targets = len(self.target_vars)
        plt.figure(figsize=(6 * n_targets, 5))

        for i, target in enumerate(self.target_vars):
            plt.subplot(1, n_targets, i + 1)
            sns.countplot(x=target, data=self.df)
            plt.title(f"Distribution of {target}")

        self._save_plot("target_distribution.png")

    def save_feature_distribution(self) -> None:
        """
        특정 데이터프레임 내의 특징 분포를 시각화하고 저장하는 함수입니다.
        주어진 특징(target 변수 제외)에 대해 분포를 표현하는 그래프를 생성하며,
        범주형 변수 또는 고유값이 적은 변수는 막대 그래프(countplot)를,
        연속형 변수는 히스토그램(histplot)을 사용하여 시각화합니다.
        결과 이미지는 지정된 파일 이름으로 저장됩니다.
        """
        cols_to_plot = [col for col in self.df.columns if col not in self.target_vars]
        n_cols = 4
        n_rows = (len(cols_to_plot) + n_cols - 1) // n_cols

        plt.figure(figsize=(20, n_rows * 4))

        for idx, col in enumerate(cols_to_plot, start=1):
            plt.subplot(n_rows, n_cols, idx)
            if self._is_categorical_dtype(col):
                sns.countplot(x=col, data=self.df)
                plt.xticks(rotation=45)
            else:
                sns.histplot(data=self.df, x=col, kde=True)
            plt.title(f"Distribution of {col}")

        self._save_plot("feature_distribution.png")

    def save_correlation_matrix(self) -> None:
        """
        모든 특징(feature)의 상관 행렬을 시각화한 결과를 이미지 파일로 저장합니다.

        이 함수는 상관 행렬을 계산하고, 이를 시각적으로 표현하기 위해
        seaborn의 heatmap을 사용합니다.
        상관 행렬의 상삼각 부분에 대해 마스크를 적용하여 반복적인 값을
        숨길 수 있도록 처리합니다. 생성된 플롯은 파일로 저장됩니다.
        """
        corr = self.correlation_matrix
        plt.figure(figsize=(20, 18))

        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=False, cmap="coolwarm", fmt=".2f", square=True, center=0)

        plt.title("Correlation Matrix (All Features)")
        self._save_plot("all_variables_correlation_matrix.png")

    def get_top_correlated_features(
        self,
        target: str,
        top_k: int = 20,
    ) -> list[str]:
        """
        주어진 타겟 변수에 대해 가장 상관 계수가 높은 변수들을 추출하는 함수.

        이 함수는 상관 계수 행렬에서 지정된 타겟 변수와의 상관 계수를 기준으로
        절대값을 계산한 뒤, 타겟변수의 열과 직접적으로 상관 계수를 가지는 다른 변수의 열중에서
        상위 K개의 열을 추출하여 변수 이름을 반환합니다.
        """
        return (
            self.correlation_matrix[target].drop(target).abs().sort_values(ascending=False).head(top_k).index.tolist()
        )

    def save_top_feature_plots(self, top_k: int = 20) -> None:
        """
        상관관계가 높은 상위 top_k 개의 변수에 대한 플롯을 저장합니다.
        """
        for target in self.target_vars:
            top_features = self.get_top_correlated_features(target, top_k=top_k)
            for feature in top_features:
                plt.figure(figsize=(8, 6))
                if self._is_categorical_dtype(feature):
                    sns.countplot(data=self.df, x=feature, hue=target)
                    plt.xticks(rotation=45)
                else:
                    sns.boxplot(data=self.df, x=target, y=feature)
                plt.title(f"{feature} by {target}")
                self._save_plot(f"{feature}_by_{target}.png")

    def save_missing_value_plot(self) -> None:
        """
        주어진 데이터프레임에서 결측치가 존재하는 열들을 추출하여, 각 열의 결측치 비율과 개수를 계산합니다.
        이를 기준으로 결측치 비율이 높은 순서대로 시각화한 막대 그래프를 생성하고, 생성된 그래프를 파일로 저장합니다.
        """
        missing = self._get_missing_summary()
        missing = missing[missing["missing_count"] > 0]

        # 결측치가 없는 데이터셋의 경우 리턴
        if missing.empty:
            return

        missing = missing.sort_values("missing_ratio", ascending=False)

        plt.figure(figsize=(12, 8))

        missing["missing_ratio"].plot.barh()
        plt.title("Missing Value Ratio by Column")
        plt.xlabel("Missing Ratio")

        self._save_plot("missing_value_ratio.png")

    def save_missing_value_summary_to_csv(self) -> None:
        """
        데이터프레임의 결측치 개수와 비율을 계산한 요약 정보를 생성하고, 이를 지정된
        디렉토리에 CSV 파일로 저장합니다.
        """
        missing = self._get_missing_summary()
        missing.to_csv(self.csv_dir / "missing_values.csv")

    def save_summary_statistics_to_csv(self, filename: str = "summary_statistics_all") -> None:
        """
        지정된 파일 이름으로 요약 통계량을 CSV 파일로 저장합니다. 모든 변수에 대한 통계량이 포함됩니다.
        """
        self.df.describe(include="all").to_csv(self.csv_dir / f"{filename}.csv")

    def save_correlation_values_to_csv(self, filename: str = "correlation_values") -> None:
        """
        지정된 파일 이름으로 상관관계 수치를 CSV 파일로 저장합니다.
        """
        self.correlation_matrix.to_csv(self.csv_dir / f"{filename}.csv")

    def _is_categorical_dtype(self, col: str) -> bool:
        """
        주어진 열이 범주형 데이터 유형인지 여부를 반환합니다.

        :param col: 데이터프레임의 열 이름
        :return: 열이 범주형 데이터 유형인 경우 True, 그렇지 않으면 False
        """
        return col in self.categorical_cols

    def _get_missing_summary(self) -> pd.DataFrame:
        missing = self.df.isnull().sum().to_frame("missing_count")
        missing["missing_ratio"] = missing["missing_count"] / len(self.df)

        return missing
