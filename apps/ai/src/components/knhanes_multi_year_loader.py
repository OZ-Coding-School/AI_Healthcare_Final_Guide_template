import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.logger import configure_logger
from src.components.data_loader import DataLoader
from src.knhanes_merge_configs import (
    HE_HP_HYPERTENSION_CODE_BY_YEAR,
    KNHANES_ADULT_MIN_AGE,
    KNHANES_EXPECTED_CODES_MAP,
    KNHANES_RAW_FILE_TEMPLATE,
    KNHANES_REQUIRED_VARS,
    KNHANES_SURVEY_YEARS,
)

logger = configure_logger("KNHANES Loader")

YEAR_VAR = "year"
PERSON_ID_VAR = "ID"
HOUSEHOLD_ID_VAR = "ID_fam"
AGE_VAR = "age"
OFFICIAL_HYPERTENSION_VAR = "HE_HP"


class KnhanesDataValidationError(ValueError):
    """KNHANES 원시 데이터가 병합 조건을 충족하지 못할 때 발생합니다."""


@dataclass(frozen=True)
class KnhanesQualityReport:
    yearly_summary: pd.DataFrame
    missing_rates: pd.DataFrame
    unexpected_codes: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        return {
            "yearly_summary": self.yearly_summary.to_dict(orient="records"),
            "adult_missing_rates": {
                var_name: {str(year): rate for year, rate in rates.items()}
                for var_name, rates in self.missing_rates.to_dict(orient="index").items()
            },
            "unexpected_codes": self.unexpected_codes.to_dict(orient="records"),
        }

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class KnhanesMultiYearLoader:
    def __init__(
        self,
        raw_data_dir: Path,
        years: Sequence[int] = tuple(KNHANES_SURVEY_YEARS),
        file_template: str = KNHANES_RAW_FILE_TEMPLATE,
        data_loader: DataLoader | None = None,
        strict_codes: bool = False,
    ) -> None:
        if not years:
            raise ValueError("At least one survey year is required")
        if len(years) != len(set(years)):
            raise ValueError(f"Survey years must be unique: {list(years)}")
        unsupported_years = sorted(set(years) - set(KNHANES_SURVEY_YEARS))
        if unsupported_years:
            raise ValueError(f"Unsupported survey years: {unsupported_years}")

        self.raw_data_dir = raw_data_dir
        self.years = sorted(years)
        self.file_template = file_template
        self.data_loader = data_loader or DataLoader()
        self.strict_codes = strict_codes

    def load(self) -> tuple[pd.DataFrame, KnhanesQualityReport]:
        """
        연도별 원시 파일을 검증한 뒤 필수 변수만 병합합니다.

        1. 연도별 파일 존재 확인
        2. 연도별 필수 컬럼과 조사연도 검증
        3. 필수 변수만 추출해 병합
        4. 개인·가구 식별자의 중복 검증
        5. 연도별 품질 리포트 생성
        """
        self._validate_files_exist()

        yearly_dfs = [self._load_year(year) for year in self.years]
        merged_df = pd.concat(yearly_dfs, ignore_index=True)

        self._validate_identifiers(merged_df)

        report = self._build_quality_report(merged_df)
        self._handle_unexpected_codes(report.unexpected_codes)

        return merged_df, report

    def _file_path(self, year: int) -> Path:
        return self.raw_data_dir / self.file_template.format(yy=f"{year % 100:02d}")

    def _validate_files_exist(self) -> None:
        missing_files = [str(self._file_path(year)) for year in self.years if not self._file_path(year).exists()]
        if missing_files:
            raise FileNotFoundError(f"KNHANES raw files not found: {missing_files}")

    def _load_year(self, year: int) -> pd.DataFrame:
        raw_df = self.data_loader.load(self._file_path(year))
        if raw_df.empty:
            raise KnhanesDataValidationError(f"{year}: raw file has no rows")

        year_df = self._normalize_column_names(raw_df)

        missing_vars = [var_name for var_name in KNHANES_REQUIRED_VARS if var_name not in year_df.columns]
        if missing_vars:
            raise KnhanesDataValidationError(f"{year}: missing required columns: {missing_vars}")

        year_df = year_df[KNHANES_REQUIRED_VARS].copy()
        return self._validate_survey_year(year_df, year)

    @staticmethod
    def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        연도별로 대소문자만 다른 컬럼을 설정의 변수명으로 맞춥니다.
        """
        columns = set(df.columns)
        columns_by_lower: dict[str, list[str]] = {}
        for column in df.columns:
            columns_by_lower.setdefault(str(column).lower(), []).append(column)

        rename_map: dict[str, str] = {}
        for var_name in KNHANES_REQUIRED_VARS:
            if var_name in columns:
                continue
            candidates = columns_by_lower.get(var_name.lower(), [])
            if len(candidates) > 1:
                raise KnhanesDataValidationError(f"Ambiguous columns for {var_name}: {candidates}")
            if candidates:
                rename_map[candidates[0]] = var_name

        return df.rename(columns=rename_map)

    @staticmethod
    def _validate_survey_year(df: pd.DataFrame, year: int) -> pd.DataFrame:
        survey_years = pd.to_numeric(df[YEAR_VAR], errors="coerce")
        mismatched = survey_years.ne(year)
        if mismatched.any():
            raise KnhanesDataValidationError(
                f"{year}: {int(mismatched.sum())} rows have a different survey year: "
                f"{sorted(df.loc[mismatched, YEAR_VAR].astype(str).unique())[:5]}"
            )

        df[YEAR_VAR] = survey_years.astype(int)
        return df

    @staticmethod
    def _validate_identifiers(df: pd.DataFrame) -> None:
        missing_identifiers = [var_name for var_name in (PERSON_ID_VAR, HOUSEHOLD_ID_VAR) if df[var_name].isna().any()]
        if missing_identifiers:
            raise KnhanesDataValidationError(f"Identifier columns contain missing values: {missing_identifiers}")

        duplicated_person_count = int(df[PERSON_ID_VAR].duplicated().sum())
        if duplicated_person_count:
            raise KnhanesDataValidationError(f"Duplicated {PERSON_ID_VAR}: {duplicated_person_count} rows")

        # 연도 홀드아웃으로 나눌 때 같은 가구가 Train과 Test에 함께 들어가지 않아야 합니다.
        years_per_household = df.groupby(HOUSEHOLD_ID_VAR)[YEAR_VAR].nunique()
        multi_year_household_count = int(years_per_household.gt(1).sum())
        if multi_year_household_count:
            raise KnhanesDataValidationError(f"{HOUSEHOLD_ID_VAR} spans multiple years: {multi_year_household_count}")

    def _build_quality_report(self, df: pd.DataFrame) -> KnhanesQualityReport:
        return KnhanesQualityReport(
            yearly_summary=self._build_yearly_summary(df),
            missing_rates=self._build_missing_rates(df),
            unexpected_codes=self._find_unexpected_codes(df),
        )

    def _build_yearly_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for year in self.years:
            year_df = df[df[YEAR_VAR].eq(year)]
            hypertension_code = HE_HP_HYPERTENSION_CODE_BY_YEAR[year]
            rows.append(
                {
                    "year": year,
                    "rows": len(year_df),
                    "adults": int(year_df[AGE_VAR].ge(KNHANES_ADULT_MIN_AGE).sum()),
                    "households": int(year_df[HOUSEHOLD_ID_VAR].nunique()),
                    "official_hypertension_code": hypertension_code,
                    "official_hypertension_rows": int(year_df[OFFICIAL_HYPERTENSION_VAR].eq(hypertension_code).sum()),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _build_missing_rates(df: pd.DataFrame) -> pd.DataFrame:
        adults = df[df[AGE_VAR].ge(KNHANES_ADULT_MIN_AGE)]
        missing_rates = adults[KNHANES_REQUIRED_VARS].drop(columns=YEAR_VAR).isna().groupby(adults[YEAR_VAR]).mean()
        return missing_rates.T.round(4)

    @staticmethod
    def _expected_codes(var_name: str, year: int) -> set[int]:
        if var_name == OFFICIAL_HYPERTENSION_VAR:
            return set(range(1, HE_HP_HYPERTENSION_CODE_BY_YEAR[year] + 1))
        return KNHANES_EXPECTED_CODES_MAP[var_name]

    def _find_unexpected_codes(self, df: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for year in self.years:
            year_df = df[df[YEAR_VAR].eq(year)]
            for var_name in [*KNHANES_EXPECTED_CODES_MAP, OFFICIAL_HYPERTENSION_VAR]:
                expected_codes = self._expected_codes(var_name, year)
                code_counts = year_df[var_name].value_counts()
                rows.extend(
                    {"year": year, "variable": var_name, "code": code, "count": int(count)}
                    for code, count in code_counts.items()
                    if code not in expected_codes
                )

        return pd.DataFrame(rows, columns=["year", "variable", "code", "count"])

    def _handle_unexpected_codes(self, unexpected_codes: pd.DataFrame) -> None:
        if unexpected_codes.empty:
            return

        message = f"Unexpected KNHANES codes: {unexpected_codes.to_dict(orient='records')}"
        if self.strict_codes:
            raise KnhanesDataValidationError(message)
        logger.warning(message)
