import platform
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def setup_korean_font() -> None:
    system_name = platform.system()
    if system_name == "Darwin":
        plt.rcParams["font.family"] = "AppleGothic"
    elif system_name == "Windows":
        plt.rcParams["font.family"] = "Malgun Gothic"
    else:  # Linux / Docker
        plt.rcParams["font.family"] = ["NanumGothic", "DejaVu Sans", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False


setup_korean_font()


class DataAnalyzer:
    def __init__(
        self,
        df: pd.DataFrame,
        output_dir_path: Path | str,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Expected pandas DataFrame")
        if df.empty:
            raise ValueError("DataFrame is empty")
        self.df = df
        output_dir = Path(output_dir_path)
        self.plot_dir = output_dir / "plots"
        self.plot_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir = output_dir / "csv"
        self.csv_dir.mkdir(parents=True, exist_ok=True)

    def run_full_eda(self, target: str | None = None) -> None:
        # 데이터셋 요약 통계량 csv 저장
        self.save_dataset_summary_to_csv()

        # 모든 피처에 대한 요약 통계량을 csv로 저장
        self.save_all_features_summary_statistics_to_csv()
        # 모든 피처의 분포를 나타낸 플롯 이미지들을 저장
        self.save_all_features_distribution_plot()
        # 모든 피처의 상관계수 행렬을 시각화 이미지로 저장
        self.save_all_features_correlation_matrix()

        # 결측치 비율을 플롯이미지들로 저장
        self.save_missing_values_summary_to_plot()
        # 결측치 요약 통계량을 csv로 저장
        self.save_missing_values_summary_to_csv()

        # 만약 타겟 피처가 주어진 경우
        if target is not None:
            # 1. 상관관계 행렬과 상관관계가 높은 top_k 개 피처의 플롯 이미지를 저장
            self.save_top_k_correlation_matrix_plot(target=target)
            # 2. 상관관계가 높은 top_k 개 피처들 간 상관계수 행렬을 시각화 이미지를 저장
            self.save_top_k_correlated_feature_plots(target=target)

    def get_dataset_summary(self) -> pd.DataFrame:
        """
        데이터셋의 요약 정보를 반환합니다.
        """
        row_count = len(self.df)
        column_count = len(self.df.columns)
        numeric_feature_count = len(self.df.select_dtypes(include=["number"]).columns)
        categorical_feature_count = len(self.df.select_dtypes(include=["object", "string", "category"]).columns)

        duplicated_row_count = self.df.duplicated().sum()

        summary = {
            "Row Count": row_count,
            "Column Count": column_count,
            "Numeric Feature Count": numeric_feature_count,
            "Categorical Feature Count": categorical_feature_count,
            "Duplicated Row Count": duplicated_row_count,
        }

        return pd.DataFrame(
            summary.items(),
            columns=["Feature", "Value"],
        )

    def save_dataset_summary_to_csv(self, filename: str = "dataset_summary.csv") -> None:
        """
        데이터셋의 요약 정보를 CSV 파일로 저장합니다.
        """
        summary_stats = self.get_dataset_summary()
        summary_stats.to_csv(self.csv_dir / filename, index=False)

    def get_all_features_summary_statistics(self) -> pd.DataFrame:
        """
        모든 변수에 대한 요약 통계량을 DataFrame으로 반환합니다.
        """
        return self.df.describe(include="all")

    def save_all_features_summary_statistics_to_csv(
        self, filename: str = "all_features_summary_statistics.csv"
    ) -> None:
        """
        모든 변수에 대한 요약 통계량을 CSV 파일로 저장합니다.
        """
        summary_stats = self.get_all_features_summary_statistics()
        summary_stats.to_csv(self.csv_dir / filename, index=True)

    def save_all_features_distribution_plot(self) -> None:
        """
        주어진 데이터프레임의 각 열의 분포를 시각화하고, 해당 그래프를 파일로 저장합니다.

        이 메서드는 데이터프레임의 모든 열에 대해서 카테고리형 데이터인 경우
        카운트 플롯을 생성하며, 수치형 데이터인 경우 히스토그램과 커널 밀도
        추정 그래프를 생성합니다. 생성된 그래프는 이미지 파일로 저장됩니다.
        """
        cols_to_plot = [col for col in self.df.columns]

        for col in cols_to_plot:
            plt.figure(figsize=(8, 6))
            if self._is_categorical_dtype(col):
                sns.countplot(x=col, data=self.df)
                plt.xticks(rotation=45)
            else:
                sns.histplot(data=self.df, x=col, kde=True)
            plt.title(f"Distribution of {col}")
            self._save_plot(f"{col}_distribution.png")

    def save_all_features_correlation_matrix(self) -> None:
        """
        모든 특징(feature)의 상관 행렬을 시각화한 결과를 이미지 파일로 저장합니다.

        이 함수는 상관 행렬을 계산하고, 이를 시각적으로 표현하기 위해
        seaborn의 heatmap을 사용합니다.
        상관 행렬의 상삼각 부분에 대해 마스크를 적용하여 반복적인 값을
        숨길 수 있도록 처리합니다. 생성된 플롯은 파일로 저장됩니다.
        """
        corr = self._create_correlation_df(self.df).corr(numeric_only=True)
        plt.figure(figsize=(20, 18))

        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=False, cmap="coolwarm", fmt=".2f", square=True, center=0)

        plt.title("Correlation Matrix (All Features)")
        self._save_plot("all_variables_correlation_matrix.png")

    def get_missing_values_summary(self) -> pd.DataFrame:
        """
        결측치가 존재하는 모든 변수의 결측치 개수와 비율을 계산한 요약 정보를 DataFrame으로 반환합니다.
        """
        missing = self.df.isnull().sum().to_frame("missing_count")
        missing["missing_ratio"] = missing["missing_count"] / len(self.df)

        return missing

    def save_missing_values_summary_to_plot(self) -> None:
        """
        주어진 데이터프레임에서 결측치가 존재하는 열들을 추출하여, 각 열의 결측치 비율과 개수를 계산합니다.
        이를 기준으로 결측치 비율이 높은 순서대로 시각화한 막대 그래프를 생성하고, 생성된 그래프를 파일로 저장합니다.
        """
        missing = self.get_missing_values_summary()
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

    def save_missing_values_summary_to_csv(self, filename: str = "missing_value_summary.csv") -> None:
        missing = self.get_missing_values_summary()
        missing.to_csv(self.csv_dir / filename)

    def save_variable_distribution_plot(self, target: str) -> None:
        """
        입력받은 변수의 분포를 시각화하여 파일로 저장합니다.
        """
        if target not in self.df.columns:
            raise ValueError(f"Target variable '{target}' not found in the DataFrame")

        plt.figure(figsize=(8, 6))
        sns.countplot(x=target, data=self.df)
        plt.title(f"Distribution of {target}")

        self._save_plot(f"{target}_distribution.png")

    def get_top_k_correlated_features(self, target: str, top_k: int = 20) -> list[str]:
        """
        주어진 타겟 변수에 대해 가장 상관 계수가 높은 변수들을 추출하는 함수.

        이 함수는 상관 계수 행렬에서 지정된 타겟 변수와의 상관 계수를 기준으로
        절대값을 계산한 뒤, 타겟변수의 열과 직접적으로 상관 계수를 가지는 다른 변수의 열중에서
        상위 K개의 열을 추출하여 변수 이름을 반환합니다.
        """
        if target not in self.df.columns:
            raise ValueError(f"Target variable '{target}' not found in the DataFrame")

        correlation_df = self._create_correlation_df(self.df)
        if target not in correlation_df.columns:
            raise ValueError(f"Target variable '{target}' must have a numeric dtype for Pearson correlation")

        corr_matrix = correlation_df.corr()
        return corr_matrix[target].drop(target).abs().sort_values(ascending=False).head(top_k).index.tolist()

    def save_top_k_correlation_matrix_plot(self, target: str, top_k: int = 20) -> None:
        """
        타겟 변수와 상관관계가 높은 tok_k개의 상관 행렬을 시각화한 결과를 이미지 파일로 저장합니다.

        이 함수는 상관 행렬을 계산하고, 이를 시각적으로 표현하기 위해 seaborn의 heatmap을 사용합니다.
        상관 행렬의 상삼각 부분에 대해 마스크를 적용하여 반복적인 값을 숨길 수 있도록 처리합니다.
        생성된 플롯은 파일로 저장됩니다.
        """
        top_k_features = self.get_top_k_correlated_features(target=target, top_k=top_k)
        top_k_df = self.df[top_k_features]
        corr = self._create_correlation_df(top_k_df).corr(numeric_only=True)
        plt.figure(figsize=(20, 18))

        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=False, cmap="coolwarm", fmt=".2f", square=True, center=0)

        plt.title(f"Correlation Matrix (TOP {top_k} Features)")
        self._save_plot("top_k_variables_correlation_matrix.png")

    def save_top_k_correlated_feature_plots(self, target: str, top_k: int = 20) -> None:
        """
        지정된 대상 변수와 가장 높은 상관 관계를 가지는 상위 feature들을 시각화하고 분석 결과를 저장합니다.
        """
        if target not in self.df.columns:
            raise ValueError(f"Target variable '{target}' is not in the DataFrame")

        top_features = self.get_top_k_correlated_features(target=target, top_k=top_k)
        for feature in top_features:
            plt.figure(figsize=(8, 6))
            if self._is_categorical_dtype(feature):
                sns.countplot(data=self.df, x=feature, hue=target)
                plt.xticks(rotation=45)
            else:
                sns.boxplot(data=self.df, x=target, y=feature)
            plt.title(f"{feature} by {target}")
            self._save_plot(f"{feature}_by_{target}.png")

    def _is_categorical_dtype(self, col: str) -> bool:
        """
        주어진 열이 범주형 데이터 유형인지 여부를 반환합니다.
        """
        if col not in self.df.columns:
            raise ValueError(f"Column '{col}' not found in the DataFrame")

        return self.df[col].dtype.name in ["category", "object"]

    def _create_correlation_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pearson 상관관계 계산에 사용할 수치형 변수만 반환합니다.
        명목형 범주를 임의의 숫자로 바꾸면 숫자 코드 순서가 상관계수에 영향을 주므로 포함하지 않습니다.
        """
        return df.select_dtypes(include=["number"]).copy()

    def _save_plot(self, filename: str) -> None:
        plt.tight_layout()
        plt.savefig(self.plot_dir / filename, dpi=300, bbox_inches="tight")
        plt.close()
