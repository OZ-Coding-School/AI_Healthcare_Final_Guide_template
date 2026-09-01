from pathlib import Path

import pandas as pd
import pytest

from src.components.data_loader import DataLoader, UnsupportedFileTypeError


def test_data_loader_csv(tmp_path: Path):
    file_path = tmp_path / "test.csv"
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    df.to_csv(file_path, index=False)

    loader = DataLoader()
    loaded_df = loader.load(file_path)

    pd.testing.assert_frame_equal(df, loaded_df)


def test_data_loader_parquet(tmp_path: Path):
    file_path = tmp_path / "test.parquet"
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    df.to_parquet(file_path, index=False)

    loader = DataLoader()
    loaded_df = loader.load(file_path)

    pd.testing.assert_frame_equal(df, loaded_df)


def test_data_loader_excel(tmp_path: Path):
    pytest.importorskip("openpyxl")
    file_path = tmp_path / "test.xlsx"
    df = pd.DataFrame({"a": [1, 2], "b": [10.5, 20.5]})
    df.to_excel(file_path, index=False)

    loader = DataLoader()
    loaded_df = loader.load(file_path)

    pd.testing.assert_frame_equal(df, loaded_df)


def test_data_loader_unsupported_file_type(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello")

    loader = DataLoader()
    with pytest.raises(UnsupportedFileTypeError, match="Unsupported file type: .txt"):
        loader.load(file_path)


def test_data_loader_file_not_found():
    loader = DataLoader()
    with pytest.raises(FileNotFoundError, match="Data file not found"):
        loader.load("non_existing_file.csv")


def test_data_loader_encoding(tmp_path: Path):
    file_path = tmp_path / "test_cp949.csv"
    df = pd.DataFrame({"한글": ["가", "나"]})
    df.to_csv(file_path, index=False, encoding="CP949")

    loader = DataLoader()
    loaded_df = loader.load(file_path, encoding="CP949")
    pd.testing.assert_frame_equal(df, loaded_df)
