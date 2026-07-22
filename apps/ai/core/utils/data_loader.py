from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast

import pyreadstat as prs
import pandas as pd
from pyreadstat import metadata_container


VALID_DATE_SET_FILE_EXT = (
    ".sas7bdat",
    ".csv",
    ".xlsx",
    ".xls",
    ".parquet",
)


class UnsupportedFileType(Exception):
    def __init__(self, ext: str) -> None:
        super().__init__(f"Unsupported file type: {ext}, supported types: {','.join(VALID_DATE_SET_FILE_EXT)}")


@dataclass
class Dataset:
    df: pd.DataFrame
    metadata: Optional[metadata_container] = None


class DataLoader:
    def load(
        self,
        data_file: str,
        sas_catalog_file: Path | str | None = None,
    ) -> Dataset:
        data_file_ext = self._extract_file_ext(data_file)
        match data_file_ext:
            case ".sas7bdat":
                if sas_catalog_file:
                    self._validate_sas_catalog_file_ext(sas_catalog_file)
                df, metadata = prs.read_sas7bdat(
                    data_file,
                    catalog_file=sas_catalog_file if sas_catalog_file else None,
                )
                df = cast(pd.DataFrame, df)
                return Dataset(df=df, metadata=metadata)
            case ".csv":
                return Dataset(pd.read_csv(data_file))
            case ".xlsx", ".xls":
                return Dataset(df=pd.read_excel(data_file))
            case ".parquet":
                return Dataset(df=pd.read_parquet(data_file))
            case _:
                raise UnsupportedFileType(data_file_ext)

    @staticmethod
    def _extract_file_ext(file_path: Path | str) -> str:
        return Path(file_path).suffix.lower()

    def _validate_sas_catalog_file_ext(self, file_path: Path | str) -> None:
        ext = self._extract_file_ext(file_path)
        if not ext or ext != ".sas7bcat":
            raise UnsupportedFileType(ext)
