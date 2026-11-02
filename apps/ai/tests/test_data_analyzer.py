from pathlib import Path

import pandas as pd
import pytest

from src.components.data_analyzer import DataAnalyzer


@pytest.fixture
def sample_eda_df():
    return pd.DataFrame(
        {
            "age": [20, 30, 40, 50, 60, None],
            "income": [2000, 3000, 4000, 5000, 6000, 7000],
            "category": ["A", "B", "A", "B", "C", "A"],
            "target": [0, 0, 1, 1, 1, 0],
        }
    )


def test_data_analyzer_init_validation(tmp_path: Path):
    with pytest.raises(TypeError):
        DataAnalyzer("not_df", tmp_path)  # type: ignore

    with pytest.raises(ValueError):
        DataAnalyzer(pd.DataFrame(), tmp_path)


def test_data_analyzer_run_full_eda(sample_eda_df, tmp_path: Path):
    analyzer = DataAnalyzer(df=sample_eda_df, output_dir_path=tmp_path)
    analyzer.run_full_eda(target="target")

    # CSV 결과 파일 확인
    assert (tmp_path / "csv/dataset_summary.csv").exists()
    assert (tmp_path / "csv/all_features_summary_statistics.csv").exists()
    assert (tmp_path / "csv/missing_value_summary.csv").exists()

    # 플롯 결과 파일 확인
    assert (tmp_path / "plots/missing_value_ratio.png").exists()
    assert (tmp_path / "plots/all_variables_correlation_matrix.png").exists()
    assert (tmp_path / "plots/top_k_variables_correlation_matrix.png").exists()
    assert (tmp_path / "plots/age_distribution.png").exists()
    assert (tmp_path / "plots/category_distribution.png").exists()
