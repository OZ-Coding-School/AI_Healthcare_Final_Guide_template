import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import settings
from src.components.data_loader import DataLoader
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError, KnhanesMultiYearLoader
from src.enums import ModelType
from src.knhanes_merge_configs import (
    HE_HP_HYPERTENSION_CODE_BY_YEAR,
    KNHANES_EXPECTED_CODES_MAP,
    KNHANES_RAW_FILE_TEMPLATE,
    KNHANES_REQUIRED_VARS,
    KNHANES_SURVEY_YEARS,
)
from src.knhanes_preprocessing_configs import (
    MODEL_INPUT_VARS_MAP,
    MODEL_LABEL_SOURCE_VARS_MAP,
    MODEL_OFFICIAL_LABEL_VAR_MAP,
    UNUSABLE_INPUT_VARS,
)
from src.pipelines.knhanes_data_pipeline import run_knhanes_merge

CSV_TEMPLATE = "hn{yy}_all.csv"
YEARS = [2021, 2022]
REAL_DATA_DIR = settings.DATA_DIR / "raw" / "knhanes"


def make_year_df(year: int) -> pd.DataFrame:
    df = pd.DataFrame({var_name: [1.0, 1.0, 1.0] for var_name in KNHANES_REQUIRED_VARS})
    df["ID"] = [f"{year}A", f"{year}B", f"{year}C"]
    df["ID_fam"] = [f"{year}F1", f"{year}F1", f"{year}F2"]
    df["year"] = year
    df["age"] = [40, 50, 10]
    df["HE_HP"] = [3, 1, 2]
    df["HE_ht"] = [170.0, np.nan, 150.0]
    df["ignored_var"] = 0
    return df


def write_years(raw_dir: Path, frames: dict[int, pd.DataFrame]) -> None:
    for year, df in frames.items():
        df.to_csv(raw_dir / CSV_TEMPLATE.format(yy=f"{year % 100:02d}"), index=False)


def make_loader(raw_dir: Path, **kwargs) -> KnhanesMultiYearLoader:
    return KnhanesMultiYearLoader(raw_dir, years=YEARS, file_template=CSV_TEMPLATE, **kwargs)


def test_required_vars_are_unique_and_exclude_unusable_vars():
    assert len(KNHANES_REQUIRED_VARS) == len(set(KNHANES_REQUIRED_VARS))
    assert set(KNHANES_REQUIRED_VARS).isdisjoint(UNUSABLE_INPUT_VARS)


@pytest.mark.parametrize("model_type", list(ModelType))
def test_required_vars_cover_every_model_role(model_type: ModelType):
    required_vars = set(KNHANES_REQUIRED_VARS)

    assert set(MODEL_INPUT_VARS_MAP[model_type]) <= required_vars
    assert set(MODEL_LABEL_SOURCE_VARS_MAP[model_type]) <= required_vars
    assert MODEL_OFFICIAL_LABEL_VAR_MAP[model_type] in required_vars


def test_expected_codes_only_cover_required_vars():
    assert set(KNHANES_EXPECTED_CODES_MAP) <= set(KNHANES_REQUIRED_VARS)


def test_hypertension_code_is_defined_for_every_survey_year():
    assert sorted(HE_HP_HYPERTENSION_CODE_BY_YEAR) == KNHANES_SURVEY_YEARS


def test_load_merges_years_with_required_vars_only(tmp_path: Path):
    write_years(tmp_path, {year: make_year_df(year) for year in YEARS})

    merged_df, _ = make_loader(tmp_path).load()

    assert list(merged_df.columns) == KNHANES_REQUIRED_VARS
    assert len(merged_df) == 6
    assert merged_df["year"].value_counts().to_dict() == {2021: 3, 2022: 3}


def test_missing_file_lists_every_absent_year(tmp_path: Path):
    write_years(tmp_path, {2021: make_year_df(2021)})

    with pytest.raises(FileNotFoundError, match="hn22_all.csv"):
        make_loader(tmp_path).load()


def test_missing_required_column_raises_with_year(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022] = frames[2022].drop(columns=["HE_fst"])
    write_years(tmp_path, frames)

    with pytest.raises(KnhanesDataValidationError, match=r"2022: missing required columns: \['HE_fst'\]"):
        make_loader(tmp_path).load()


def test_column_case_difference_is_normalized(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022] = frames[2022].rename(columns={"HE_HDL_st2": "HE_HDL_ST2"})
    write_years(tmp_path, frames)

    merged_df, _ = make_loader(tmp_path).load()

    assert merged_df["HE_HDL_st2"].notna().all()


def test_ambiguous_column_case_raises(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022] = frames[2022].rename(columns={"HE_HDL_st2": "HE_HDL_ST2"})
    frames[2022]["he_hdl_st2"] = 1.0
    write_years(tmp_path, frames)

    with pytest.raises(KnhanesDataValidationError, match="Ambiguous columns for HE_HDL_st2"):
        make_loader(tmp_path).load()


def test_file_with_wrong_survey_year_raises(tmp_path: Path):
    write_years(tmp_path, {2021: make_year_df(2021), 2022: make_year_df(2023)})

    with pytest.raises(KnhanesDataValidationError, match="2022: 3 rows have a different survey year"):
        make_loader(tmp_path).load()


def test_empty_file_raises(tmp_path: Path):
    write_years(tmp_path, {2021: make_year_df(2021), 2022: make_year_df(2022).iloc[0:0]})

    with pytest.raises(KnhanesDataValidationError, match="2022: raw file has no rows"):
        make_loader(tmp_path).load()


def test_duplicated_person_id_raises(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022].loc[0, "ID"] = "2021A"
    write_years(tmp_path, frames)

    with pytest.raises(KnhanesDataValidationError, match="Duplicated ID: 1 rows"):
        make_loader(tmp_path).load()


def test_household_across_years_raises(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022].loc[0, "ID_fam"] = "2021F1"
    write_years(tmp_path, frames)

    with pytest.raises(KnhanesDataValidationError, match="ID_fam spans multiple years: 1"):
        make_loader(tmp_path).load()


def test_missing_identifier_raises(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022]["ID_fam"] = frames[2022]["ID_fam"].astype(object)
    frames[2022].loc[0, "ID_fam"] = None
    write_years(tmp_path, frames)

    with pytest.raises(KnhanesDataValidationError, match="contain missing values"):
        make_loader(tmp_path).load()


def test_hypertension_code_follows_year(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2022]["HE_HP"] = [4, 3, 1]
    write_years(tmp_path, frames)

    _, report = make_loader(tmp_path).load()
    summary = report.yearly_summary.set_index("year")

    assert summary.loc[2021, "official_hypertension_code"] == 3
    assert summary.loc[2021, "official_hypertension_rows"] == 1
    assert summary.loc[2022, "official_hypertension_code"] == 4
    assert summary.loc[2022, "official_hypertension_rows"] == 1
    assert report.unexpected_codes.empty


def test_unexpected_code_is_reported_by_default(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2021]["HE_HP"] = [4, 1, 2]
    write_years(tmp_path, frames)

    _, report = make_loader(tmp_path).load()

    assert report.unexpected_codes.to_dict(orient="records") == [
        {"year": 2021, "variable": "HE_HP", "code": 4, "count": 1}
    ]


def test_strict_codes_raises_on_unexpected_code(tmp_path: Path):
    frames = {year: make_year_df(year) for year in YEARS}
    frames[2021]["sex"] = [1.0, 2.0, 7.0]
    write_years(tmp_path, frames)

    with pytest.raises(KnhanesDataValidationError, match="Unexpected KNHANES codes"):
        make_loader(tmp_path, strict_codes=True).load()


def test_quality_report_counts_adults_and_households(tmp_path: Path):
    write_years(tmp_path, {year: make_year_df(year) for year in YEARS})

    _, report = make_loader(tmp_path).load()
    summary = report.yearly_summary.set_index("year")

    assert summary.loc[2021, "rows"] == 3
    assert summary.loc[2021, "adults"] == 2
    assert summary.loc[2021, "households"] == 2
    assert report.missing_rates.loc["HE_ht", 2021] == 0.5
    assert "year" not in report.missing_rates.index


def test_quality_report_saves_json(tmp_path: Path):
    write_years(tmp_path, {year: make_year_df(year) for year in YEARS})
    _, report = make_loader(tmp_path).load()
    output_path = tmp_path / "reports" / "quality.json"

    report.save(output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["yearly_summary"][0]["year"] == 2021
    assert saved["adult_missing_rates"]["HE_ht"]["2021"] == 0.5


@pytest.mark.parametrize(
    ("years", "message"),
    [
        ([], "At least one survey year"),
        ([2021, 2021], "must be unique"),
        ([2019, 2021], "Unsupported survey years"),
    ],
)
def test_invalid_years_raise(tmp_path: Path, years: list[int], message: str):
    with pytest.raises(ValueError, match=message):
        KnhanesMultiYearLoader(tmp_path, years=years)


def test_run_knhanes_merge_saves_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for year in KNHANES_SURVEY_YEARS:
        (tmp_path / KNHANES_RAW_FILE_TEMPLATE.format(yy=year % 100)).touch()
    monkeypatch.setattr(DataLoader, "load", lambda _, path: make_year_df(2000 + int(Path(path).name[2:4])))

    merged_df, _ = run_knhanes_merge(
        raw_data_dir=tmp_path,
        merged_data_path=tmp_path / "interim" / "merged.parquet",
        quality_report_path=tmp_path / "reports" / "quality.json",
    )

    assert sorted(merged_df["year"].unique()) == KNHANES_SURVEY_YEARS
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "interim" / "merged.parquet"), merged_df)
    assert (tmp_path / "reports" / "quality.json").exists()


@pytest.mark.skipif(
    not all(
        (REAL_DATA_DIR / KNHANES_RAW_FILE_TEMPLATE.format(yy=year % 100)).exists() for year in KNHANES_SURVEY_YEARS
    ),
    reason="KNHANES raw files are not available",
)
def test_real_files_match_verified_counts(tmp_path: Path):
    merged_df, report = run_knhanes_merge(
        merged_data_path=tmp_path / "merged.parquet",
        quality_report_path=tmp_path / "quality.json",
    )

    assert len(merged_df) == 34_640
    assert report.yearly_summary["adults"].sum() == 29_347
    assert report.yearly_summary["households"].sum() == 17_208
    assert (tmp_path / "merged.parquet").exists()
    assert (tmp_path / "quality.json").exists()
