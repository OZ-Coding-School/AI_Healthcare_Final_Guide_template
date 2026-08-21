from pathlib import Path
from typing import cast

import pandas as pd
import pyreadstat as prs

VALID_DATE_SET_FILE_EXT = (
    ".sas7bdat",
    ".csv",
    ".xlsx",
    ".xls",
    ".parquet",
)


class UnsupportedFileTypeError(Exception):
    def __init__(self, ext: str) -> None:
        super().__init__(f"Unsupported file type: {ext}, supported types: {','.join(VALID_DATE_SET_FILE_EXT)}")


class DataLoader:
    def load(
        self,
        data_file: Path,
    ) -> pd.DataFrame:
        data_file_ext = self._extract_file_ext(data_file)
        match data_file_ext:
            case ".sas7bdat":
                df, _ = prs.read_sas7bdat(
                    data_file,
                    encoding="CP949",
                )
                df = cast(pd.DataFrame, df)
                return df
            case ".csv":
                return pd.read_csv(data_file)
            case ".xlsx", ".xls":
                return pd.read_excel(data_file)
            case ".parquet":
                return pd.read_parquet(data_file)
            case _:
                raise UnsupportedFileTypeError(data_file_ext)

    @staticmethod
    def _extract_file_ext(file_path: Path) -> str:
        return file_path.suffix.lower()
