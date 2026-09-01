from pathlib import Path
from typing import cast

import pandas as pd
import pyreadstat as prs

VALID_DATASET_FILE_EXT = (
    ".sas7bdat",
    ".csv",
    ".xlsx",
    ".xls",
    ".parquet",
)
VALID_DATE_SET_FILE_EXT = VALID_DATASET_FILE_EXT


class UnsupportedFileTypeError(Exception):
    def __init__(self, ext: str) -> None:
        super().__init__(f"Unsupported file type: {ext}, supported types: {', '.join(VALID_DATASET_FILE_EXT)}")


class DataLoader:
    def load(
        self,
        data_file: Path | str,
        encoding: str | None = None,
    ) -> pd.DataFrame:
        path = Path(data_file)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        data_file_ext = self._extract_file_ext(path)
        match data_file_ext:
            case ".sas7bdat":
                sas_encoding = encoding or "CP949"
                df, _ = prs.read_sas7bdat(
                    path,
                    encoding=sas_encoding,
                )
                df = cast(pd.DataFrame, df)
                return df
            case ".csv":
                kwargs = {"encoding": encoding} if encoding else {}
                return pd.read_csv(path, **kwargs)
            case ".xlsx" | ".xls":
                try:
                    return pd.read_excel(path)
                except ImportError:
                    return pd.read_excel(path, engine="openpyxl")
            case ".parquet":
                return pd.read_parquet(path)
            case _:
                raise UnsupportedFileTypeError(data_file_ext)

    @staticmethod
    def _extract_file_ext(file_path: Path) -> str:
        return file_path.suffix.lower()
