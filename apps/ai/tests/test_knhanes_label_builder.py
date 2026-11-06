import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from core.config import settings
from src.components.knhanes_label_builder import KnhanesLabelBuilder
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.enums import ModelType
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.pipelines.knhanes_data_pipeline import run_knhanes_labeling

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK
REAL_MERGED_DATA_PATH = settings.DATA_DIR / "interim" / "knhanes_2020_2024.parquet"


def make_row(**overrides: Any) -> dict[str, Any]:
    """두 질환 모두 음성으로 판정되는 성인 1명의 기본값입니다."""
    return {
        "ID": "A1",
        "ID_fam": "F1",
        "year": 2022,
        "age": 40.0,
        "HE_prg": 0.0,
        "HE_dprg": np.nan,
        "DE1_dg": 0.0,
        "DE1_31": 8.0,
        "DE1_32": 8.0,
        "HE_glu": 90.0,
        "HE_fst": 12.0,
        "HE_HbA1c": 5.2,
        "HE_DM_HbA1c": 1.0,
        "DI1_pr": 8.0,
        "DI1_2": 8.0,
        "HE_sbp": 110.0,
        "HE_dbp": 70.0,
        "HE_HP": 1.0,
        "HE_ht": 170.0,
    } | overrides


def make_df(*rows: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["ID"] = [f"A{index}" for index in range(len(df))]
    return df


def build(df: pd.DataFrame, model_type: ModelType) -> pd.DataFrame:
    labeled_df, _ = KnhanesLabelBuilder(strict_official_match=False).build(df, model_type)
    return labeled_df


def label_of(model_type: ModelType, **overrides: Any) -> int | None:
    """기본 행에 값을 덮어쓴 뒤 라벨을 반환합니다. 판정할 수 없으면 None입니다."""
    labeled_df = build(make_df(make_row(**overrides), make_row()), model_type)
    labels = labeled_df.loc[labeled_df["ID"].eq("A0"), DISEASE_LABEL_VAR]
    return None if labels.empty else int(labels.iloc[0])


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"HE_glu": 126.0}, 1),
        ({"HE_glu": 125.0}, 0),
        ({"HE_HbA1c": 6.5}, 1),
        ({"HE_HbA1c": 6.4}, 0),
        ({"DE1_dg": 1.0}, 1),
        ({"DE1_31": 1.0, "DE1_dg": 0.0}, 1),
        ({"DE1_32": 1.0, "DE1_dg": 0.0}, 1),
    ],
)
def test_diabetes_label_criteria(overrides: dict[str, Any], expected: int):
    assert label_of(D, **overrides) == expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"HE_sbp": 140.0}, 1),
        ({"HE_sbp": 139.9}, 0),
        ({"HE_dbp": 90.0}, 1),
        ({"HE_dbp": 89.9}, 0),
        ({"DI1_2": 1.0}, 1),
        ({"DI1_2": 4.0}, 1),
        ({"DI1_2": 5.0}, 0),
        ({"DI1_pr": 1.0}, 1),
    ],
)
def test_hypertension_label_criteria(overrides: dict[str, Any], expected: int):
    assert label_of(H, **overrides) == expected


@pytest.mark.parametrize("fasting_hours", [7.9, 0.0, np.nan])
def test_non_fasting_glucose_is_not_used_as_positive_or_negative(fasting_hours: float):
    assert label_of(D, HE_glu=200.0, HE_fst=fasting_hours) is None
    assert label_of(D, HE_glu=90.0, HE_fst=fasting_hours) is None


def test_exactly_eight_hours_counts_as_fasting():
    assert label_of(D, HE_glu=126.0, HE_fst=8.0) == 1


def test_non_fasting_person_can_be_positive_by_other_criteria():
    assert label_of(D, HE_glu=90.0, HE_fst=2.0, HE_HbA1c=6.5) == 1


def test_non_fasting_glucose_is_masked_in_hypertension_data():
    labeled_df = build(make_df(make_row(HE_glu=150.0, HE_fst=3.0)), H)

    assert labeled_df["HE_glu"].isna().all()


@pytest.mark.parametrize(
    ("model_type", "overrides"),
    [
        (D, {"HE_glu": np.nan}),
        (D, {"HE_HbA1c": np.nan}),
        (D, {"DE1_dg": 9.0}),
        (D, {"DE1_dg": np.nan}),
        (D, {"DE1_31": 9.0}),
        (D, {"DE1_32": 9.0}),
        (H, {"HE_sbp": np.nan}),
        (H, {"HE_dbp": np.nan}),
        (H, {"DI1_pr": 9.0}),
        (H, {"DI1_pr": np.nan}),
        (H, {"DI1_2": 9.0}),
    ],
)
def test_unconfirmed_negative_is_excluded(model_type: ModelType, overrides: dict[str, Any]):
    assert label_of(model_type, **overrides) is None


@pytest.mark.parametrize(
    ("model_type", "overrides"),
    [
        (D, {"HE_HbA1c": 7.0, "HE_glu": np.nan, "DE1_dg": 9.0}),
        (H, {"HE_sbp": 150.0, "HE_dbp": np.nan, "DI1_2": 9.0}),
    ],
)
def test_positive_is_kept_when_other_values_are_missing(model_type: ModelType, overrides: dict[str, Any]):
    assert label_of(model_type, **overrides) == 1


@pytest.mark.parametrize("model_type", list(ModelType))
@pytest.mark.parametrize(
    "overrides",
    [{"HE_prg": 1.0}, {"HE_prg": 0.0, "HE_dprg": 5.0}, {"age": 18.0}, {"age": np.nan}],
)
def test_pregnant_and_non_adult_rows_are_excluded(model_type: ModelType, overrides: dict[str, Any]):
    assert label_of(model_type, **overrides) is None


@pytest.mark.parametrize("model_type", list(ModelType))
def test_nineteen_year_old_is_included(model_type: ModelType):
    assert label_of(model_type, age=19.0) == 0


def test_build_keeps_input_unchanged_and_adds_integer_label():
    df = make_df(make_row(HE_glu=150.0, HE_fst=3.0), make_row())
    original = df.copy(deep=True)

    labeled_df = build(df, H)

    pd.testing.assert_frame_equal(df, original)
    assert labeled_df[DISEASE_LABEL_VAR].dtype.kind == "i"
    assert labeled_df.index.tolist() == [0, 1]
    assert set(df.columns) | {DISEASE_LABEL_VAR} == set(labeled_df.columns)


def test_official_comparison_for_diabetes():
    df = make_df(make_row(HE_HbA1c=7.0, HE_DM_HbA1c=3.0), make_row(), make_row(HE_DM_HbA1c=np.nan, DE1_dg=1.0))

    _, report = KnhanesLabelBuilder().build(df, D)

    comparison = report.official_comparison
    assert comparison["compared_rows"] == 2
    assert comparison["both_positive"] == 1
    assert comparison["both_negative"] == 1
    assert comparison["agreement_rate"] == 1.0
    assert comparison["labeled_without_official"] == 1


@pytest.mark.parametrize(("year", "official_code"), [(2021, 3), (2022, 4)])
def test_hypertension_official_code_depends_on_year(year: int, official_code: int):
    df = make_df(make_row(year=year, HE_sbp=150.0, HE_HP=float(official_code)), make_row(year=year))

    _, report = KnhanesLabelBuilder().build(df, H)

    assert report.official_comparison["both_positive"] == 1
    assert report.official_comparison["unexplained_mismatch"] == 0


def test_code_three_is_not_hypertension_from_2022():
    df = make_df(make_row(year=2022, HE_HP=3.0))

    _, report = KnhanesLabelBuilder().build(df, H)

    assert report.official_comparison["both_negative"] == 1


def test_current_prevalence_only_positive_is_a_designed_difference():
    df = make_df(make_row(DI1_pr=1.0, DI1_2=5.0, HE_HP=1.0), make_row())

    _, report = KnhanesLabelBuilder().build(df, H)

    comparison = report.official_comparison
    assert comparison["label_only_positive"] == 1
    assert comparison["designed_difference"] == 1
    assert comparison["unexplained_mismatch"] == 0
    assert comparison["agreement_rate"] == 0.5


@pytest.mark.parametrize(
    ("model_type", "row"),
    [
        (D, make_row(HE_DM_HbA1c=3.0)),
        (D, make_row(HE_HbA1c=7.0, HE_DM_HbA1c=1.0)),
        (H, make_row(HE_HP=4.0)),
        (H, make_row(HE_sbp=150.0, HE_HP=1.0)),
    ],
)
def test_official_mismatch_raises_when_strict(model_type: ModelType, row: dict[str, Any]):
    df = make_df(row)

    with pytest.raises(KnhanesDataValidationError, match="official classification"):
        KnhanesLabelBuilder().build(df, model_type)

    labeled_df, report = KnhanesLabelBuilder(strict_official_match=False).build(df, model_type)
    assert len(labeled_df) == 1
    assert report.official_comparison["unexplained_mismatch"] == 1


def test_yearly_summary_counts_every_exclusion():
    df = make_df(
        make_row(year=2021),
        make_row(year=2021, HE_prg=1.0),
        make_row(year=2021, HE_fst=2.0),
        make_row(year=2021, age=10.0),
        make_row(year=2022, HE_HbA1c=7.0, HE_DM_HbA1c=3.0),
    )

    _, report = KnhanesLabelBuilder().build(df, D)

    summary = report.yearly_summary.set_index("year")
    assert summary.loc[2021, "adults"] == 3
    assert summary.loc[2021, "pregnant_excluded"] == 1
    assert summary.loc[2021, "non_fasting_glucose_masked"] == 1
    assert summary.loc[2021, "unlabeled_excluded"] == 1
    assert summary.loc[2021, "labeled"] == 1
    assert summary.loc[2022, "positive"] == 1
    assert summary.loc[2022, "positive_rate"] == 1.0


def test_report_saves_json(tmp_path: Path):
    _, report = KnhanesLabelBuilder().build(make_df(make_row()), D)
    output_path = tmp_path / "reports" / "label.json"

    report.save(output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["model_type"] == "diabetes_risk"
    assert saved["yearly_summary"][0]["labeled"] == 1


@pytest.mark.parametrize(
    ("model_type", "column"),
    [(D, "DE1_dg"), (D, "HE_fst"), (D, "HE_DM_HbA1c"), (H, "DI1_2"), (H, "HE_HP"), (H, "HE_prg"), (H, "age")],
)
def test_missing_column_raises(model_type: ModelType, column: str):
    df = make_df(make_row()).drop(columns=column)

    with pytest.raises(KnhanesDataValidationError, match=column):
        KnhanesLabelBuilder().build(df, model_type)


def test_non_numeric_column_raises():
    df = make_df(make_row())
    df["HE_sbp"] = ["high"]

    with pytest.raises(KnhanesDataValidationError, match="must be numeric"):
        KnhanesLabelBuilder().build(df, H)


@pytest.mark.parametrize("year", [2019.0, np.nan])
def test_invalid_survey_year_raises(year: float):
    df = make_df(make_row(), make_row())
    df["year"] = [2022.0, year]

    with pytest.raises(KnhanesDataValidationError, match="invalid survey years"):
        KnhanesLabelBuilder().build(df, H)


def test_no_labelable_rows_raises():
    with pytest.raises(KnhanesDataValidationError, match="no rows"):
        KnhanesLabelBuilder().build(make_df(make_row(age=10.0)), D)


def test_run_knhanes_labeling_saves_outputs(tmp_path: Path):
    merged_path = tmp_path / "merged.parquet"
    make_df(make_row(), make_row(HE_prg=1.0)).to_parquet(merged_path, index=False)
    labeled_dir = tmp_path / "labeled"
    report_path = tmp_path / "reports" / "label.json"

    results = run_knhanes_labeling(merged_path, labeled_dir, report_path)

    assert set(results) == set(ModelType)
    for model_type, (labeled_df, _) in results.items():
        saved_df = pd.read_parquet(labeled_dir / f"{model_type}.parquet")
        pd.testing.assert_frame_equal(saved_df, labeled_df)
    assert set(json.loads(report_path.read_text(encoding="utf-8"))) == {str(model_type) for model_type in ModelType}


def test_run_knhanes_labeling_requires_merged_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Merged KNHANES data"):
        run_knhanes_labeling(tmp_path / "missing.parquet", tmp_path, tmp_path / "label.json")


@pytest.mark.skipif(not REAL_MERGED_DATA_PATH.exists(), reason="Merged KNHANES data is not available")
def test_real_data_matches_verified_counts(tmp_path: Path):
    results = run_knhanes_labeling(
        labeled_data_dir=tmp_path / "labeled",
        label_report_path=tmp_path / "label.json",
    )

    diabetes_df, diabetes_report = results[D]
    assert len(diabetes_df) == 27_404
    assert diabetes_df[DISEASE_LABEL_VAR].sum() == 4_710
    assert diabetes_report.official_comparison["compared_rows"] == 27_086
    assert diabetes_report.official_comparison["agreement_rate"] == 1.0

    hypertension_df, hypertension_report = results[H]
    assert len(hypertension_df) == 28_397
    assert hypertension_df[DISEASE_LABEL_VAR].sum() == 10_016
    assert hypertension_report.official_comparison["compared_rows"] == 28_292
    assert hypertension_report.official_comparison["designed_difference"] == 85
    assert hypertension_report.official_comparison["unexplained_mismatch"] == 0
    assert diabetes_report.yearly_summary["pregnant_excluded"].sum() == 75
