from pathlib import Path

import pandas as pd
import pytest

from src.components.data_splitter import DataSplitter, SplitData


@pytest.fixture
def sample_split_df() -> pd.DataFrame:
    # 100행 데이터 (타겟 불균형 80:20)
    return pd.DataFrame(
        {
            "feat1": range(100),
            "feat2": range(100, 200),
            "target": ["N"] * 80 + ["Y"] * 20,
        }
    )


def test_data_splitter_ratio_validation(tmp_path: Path):
    with pytest.raises(ValueError, match=r"train_size \+ val_size \+ test_size must equal 1.0"):
        DataSplitter(output_dir=tmp_path, train_size=0.5, val_size=0.2, test_size=0.2)

    with pytest.raises(ValueError, match="train_size must be between 0 and 1"):
        DataSplitter(output_dir=tmp_path, train_size=1.2, val_size=0.1, test_size=0.1)


def test_data_splitter_split_and_save(sample_split_df, tmp_path: Path):
    splitter = DataSplitter(
        output_dir=tmp_path,
        train_size=0.6,
        val_size=0.2,
        test_size=0.2,
        random_state=42,
    )

    split_data = splitter.split(sample_split_df, target_var="target")

    assert isinstance(split_data, SplitData)
    assert len(split_data.X_train) == 60
    assert len(split_data.y_train) == 60
    assert len(split_data.X_validation) == 20
    assert len(split_data.y_validation) == 20
    assert len(split_data.X_test) == 20
    assert len(split_data.y_test) == 20

    # Stratified 비율 검증 (각 세트별 Y 비율이 20% 내외로 유지되는지)
    assert split_data.y_train.value_counts(normalize=True)["Y"] == pytest.approx(0.2, abs=0.05)
    assert split_data.y_validation.value_counts(normalize=True)["Y"] == pytest.approx(0.2, abs=0.05)
    assert split_data.y_test.value_counts(normalize=True)["Y"] == pytest.approx(0.2, abs=0.05)

    # Parquet 저장 확인
    splitter.save_to_parquet(split_data)
    for name in ["X_train", "y_train", "X_validation", "y_validation", "X_test", "y_test"]:
        assert (tmp_path / f"{name}.parquet").exists()


def test_data_splitter_missing_target(sample_split_df, tmp_path: Path):
    splitter = DataSplitter(output_dir=tmp_path)
    with pytest.raises(ValueError, match="Target variable 'non_existing' not found"):
        splitter.split(sample_split_df, target_var="non_existing")


def test_data_splitter_two_way_split(sample_split_df, tmp_path: Path):
    splitter = DataSplitter(
        output_dir=tmp_path,
        train_size=0.8,
        val_size=0.0,
        test_size=0.2,
        random_state=42,
    )

    split_data = splitter.split(sample_split_df, target_var="target")
    assert isinstance(split_data, SplitData)
    assert len(split_data.X_train) == 80
    assert len(split_data.y_train) == 80
    assert len(split_data.X_validation) == 0
    assert len(split_data.y_validation) == 0
    assert len(split_data.X_test) == 20
    assert len(split_data.y_test) == 20

    splitter.save_to_parquet(split_data)
    for name in ["X_train", "y_train", "X_test", "y_test"]:
        assert (tmp_path / f"{name}.parquet").exists()
