from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import settings
from src.components.data_preprocessor import KnhanesPreprocessor
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.enums import ModelType
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.knhanes_preprocessing_configs import (
    BLOOD_INPUT_VARS,
    KNHANES_VARIABLES_CONFIG_MAP,
    MODEL_FORBIDDEN_INPUT_VARS_MAP,
    TRAINING_META_VARS,
)
from src.pipelines.knhanes_data_pipeline import run_knhanes_preprocessing

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK
REAL_LABELED_DATA_DIR = settings.DATA_DIR / "interim" / "labeled"


@pytest.fixture
def labeled_knhanes_sample_df() -> pd.DataFrame:
    """KnhanesLabelBuilder가 만든 데이터와 같은 형식의 표본입니다. 라벨 원천 변수를 함께 포함합니다."""
    return pd.DataFrame(
        {
            "ID": ["A1", "A2", "A3"],
            "ID_fam": ["F1", "F2", "F3"],
            "year": [2022, 2023, 2024],
            "wt_itvex": [1000.0, 2000.0, 3000.0],
            "wt_tot": [1100.0, 2100.0, 3100.0],
            "kstrata": [1.0, 2.0, 3.0],
            "psu": [11.0, 12.0, 13.0],
            "disease_label": [0, 1, 1],
            "sex": [1.0, 2.0, 2.0],
            "age": [45.0, 50.0, 60.0],
            "HE_ht": [170.0, 160.0, 175.0],
            "HE_wt": [70.0, 60.0, 80.0],
            "HE_wc": [85.0, 75.0, 90.0],
            "HE_BMI": [np.nan, 23.4, 26.1],
            "BD1": [2.0, 1.0, 9.0],
            "BD1_11": [3.0, 8.0, 9.0],
            "BD2_1": [2.0, 8.0, 9.0],
            "BS3_1": [1.0, 3.0, 8.0],
            "BS3_2": [10.0, 888.0, 999.0],
            "HE_chol": [190.0, 210.0, 230.0],
            "HE_HDL_st2": [50.0, 55.0, 45.0],
            "HE_TG": [120.0, 150.0, 180.0],
            "HE_ast": [25.0, 20.0, 30.0],
            "HE_alt": [22.0, 18.0, 35.0],
            "HE_crea": [1.0, 0.8, 1.1],
            "HE_Upro": [0.0, 1.0, np.nan],
            "HE_Uglu": [0.0, 5.0, np.nan],
            "DE1_dg": [0.0, 1.0, 1.0],
            "DE1_pr": [8.0, 1.0, 9.0],
            "DE1_31": [8.0, 1.0, 0.0],
            "DE1_32": [8.0, 1.0, 0.0],
            "DI1_pr": [8.0, 1.0, 9.0],
            "DI1_2": [8.0, 1.0, 5.0],
            "HE_glu": [90.0, 130.0, np.nan],
            "HE_fst": [12.0, 12.0, 4.0],
            "HE_HbA1c": [5.2, 6.8, 6.0],
            "HE_sbp": [120.0, 130.0, 145.0],
            "HE_dbp": [80.0, 85.0, 90.0],
            "HE_DM_HbA1c": [1.0, 3.0, 3.0],
            "HE_HP": [1.0, 4.0, 4.0],
            "HE_prg": [np.nan, 0.0, 0.0],
            "HE_dprg": [np.nan, np.nan, np.nan],
            "HE_DMfh1": [0.0, 1.0, 9.0],
            "HE_DMfh2": [0.0, 0.0, np.nan],
            "HE_DMfh3": [8.0, 8.0, np.nan],
            "HE_HPfh1": [0.0, 1.0, 9.0],
            "HE_HPfh2": [0.0, 0.0, np.nan],
            "HE_HPfh3": [8.0, 8.0, np.nan],
        }
    )


def make_preprocessor(model_type: ModelType, tmp_path: Path) -> KnhanesPreprocessor:
    return KnhanesPreprocessor(use_case=model_type, output_dir=tmp_path)


def forbidden_columns(model_type: ModelType) -> set[str]:
    label_by_var_name = {var["name"]: var["label"] for var in KNHANES_VARIABLES_CONFIG_MAP}
    return {label_by_var_name.get(name, name) for name in MODEL_FORBIDDEN_INPUT_VARS_MAP[model_type]}


@pytest.mark.parametrize("model_type", list(ModelType))
def test_preprocess_works_without_label_or_meta_columns(labeled_knhanes_sample_df, model_type, tmp_path: Path):
    user_df = labeled_knhanes_sample_df.drop(columns=[*TRAINING_META_VARS, DISEASE_LABEL_VAR])

    processed_df = make_preprocessor(model_type, tmp_path).preprocess(user_df)

    assert len(processed_df) == len(user_df)
    assert forbidden_columns(model_type).isdisjoint(processed_df.columns)
    assert DISEASE_LABEL_VAR not in processed_df.columns


def test_preprocess_keeps_minor_rows_for_shared_inference_rules(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[0, "age"] = 15.0

    processed_df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert len(processed_df) == 3


def test_diabetes_inputs_exclude_label_vars_and_keep_blood_pressure(labeled_knhanes_sample_df, tmp_path: Path):
    columns = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df).columns

    assert {"공복혈당", "당화혈색소", "당뇨병 유병 여부", "HE_fst", "DE1_31", "DE1_32", "DE1_dg"}.isdisjoint(columns)
    assert {"수축기 혈압", "이완기 혈압", "고혈압 유병 여부", "당뇨병 가족력 보유 여부"} <= set(columns)


def test_hypertension_inputs_exclude_label_vars_and_keep_glucose(labeled_knhanes_sample_df, tmp_path: Path):
    columns = make_preprocessor(H, tmp_path).preprocess(labeled_knhanes_sample_df).columns

    assert {"수축기 혈압", "이완기 혈압", "고혈압 유병 여부", "DI1_2"}.isdisjoint(columns)
    assert {"공복혈당", "당화혈색소", "당뇨병 유병 여부", "요당", "고혈압 가족력 보유 여부"} <= set(columns)


def test_codes_are_cleaned_from_float_values(labeled_knhanes_sample_df, tmp_path: Path):
    df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert df["성별"].astype(object).tolist() == ["M", "F", "F"]
    assert df["고혈압 유병 여부"].astype(object).tolist() == ["N", "Y", "UNKNOWN"]
    assert df["현재 흡연 여부"].astype(object).tolist() == ["CURRENT", "FORMER", "NEVER"]
    assert df["평생음주경험"].astype(object).tolist()[:2] == ["Y", "N"]
    assert df["1년간 음주빈도"].astype(object).tolist()[:2] == ["MONTHLY", "NEVER"]
    assert df["한 번에 마시는 음주량"].astype(object).tolist()[:2] == ["3~4잔", "0"]
    assert df["요단백"].astype(object).tolist()[:2] == ["-", "±"]


def test_non_response_stays_missing_for_trainer_category(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[2, "BS3_1"] = 9.0

    df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert df.loc[2, ["현재 흡연 여부", "평생음주경험", "1년간 음주빈도", "한 번에 마시는 음주량"]].isna().all()
    assert pd.isna(df.loc[2, "하루평균 담배 흡연량"])


def test_smoking_amount_not_applicable_becomes_zero(labeled_knhanes_sample_df, tmp_path: Path):
    df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert df["하루평균 담배 흡연량"].iloc[:2].tolist() == [10.0, 0.0]


def test_family_history_missing_becomes_unknown(labeled_knhanes_sample_df, tmp_path: Path):
    df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert df["당뇨병 가족력(모)"].astype(object).tolist() == ["N", "N", "UNKNOWN"]
    assert df["당뇨병 가족력(형제자매)"].astype(object).tolist() == ["NOT_APPLICABLE", "NOT_APPLICABLE", "UNKNOWN"]
    assert df["당뇨병 가족력 보유 여부"].astype(object).tolist() == ["0", "1", "UNKNOWN"]


def test_bmi_is_filled_from_height_and_weight(labeled_knhanes_sample_df, tmp_path: Path):
    df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert df["BMI"].iloc[0] == pytest.approx(70 / (1.7**2))


def test_missing_input_column_raises(labeled_knhanes_sample_df, tmp_path: Path):
    with pytest.raises(KnhanesDataValidationError, match="missing input columns"):
        make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df.drop(columns="HE_wc"))


def test_non_numeric_input_raises(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df["sex"] = ["M", "F", "F"]

    with pytest.raises(KnhanesDataValidationError, match="must be numeric"):
        make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)


def test_unexpected_input_code_raises(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[0, "BD1_11"] = 7.0

    with pytest.raises(KnhanesDataValidationError, match="unexpected input codes.*BD1_11"):
        make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)


def test_forbidden_output_column_raises(labeled_knhanes_sample_df, tmp_path: Path):
    preprocessor = make_preprocessor(D, tmp_path)
    preprocessor.usable_vars = [*preprocessor.usable_vars, "HE_HbA1c"]

    with pytest.raises(KnhanesDataValidationError, match="forbidden input columns"):
        preprocessor.preprocess(labeled_knhanes_sample_df)


def test_input_df_is_not_modified(labeled_knhanes_sample_df, tmp_path: Path):
    original_df = labeled_knhanes_sample_df.copy()

    make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)

    pd.testing.assert_frame_equal(labeled_knhanes_sample_df, original_df)


def test_preprocess_labeled_keeps_meta_and_label_in_row_order(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_df = labeled_knhanes_sample_df.set_index(pd.Index([10, 20, 30]))

    df = make_preprocessor(D, tmp_path).preprocess_labeled(labeled_df)

    assert df.columns[: len(TRAINING_META_VARS)].tolist() == TRAINING_META_VARS
    assert df["ID"].tolist() == ["A1", "A2", "A3"]
    assert df[DISEASE_LABEL_VAR].tolist() == [0, 1, 1]
    assert df["나이"].tolist() == [45.0, 50.0, 60.0]
    assert not df.columns.duplicated().any()


@pytest.mark.parametrize("missing_var", ["ID_fam", "year", "wt_tot", DISEASE_LABEL_VAR])
def test_preprocess_labeled_requires_training_columns(labeled_knhanes_sample_df, missing_var, tmp_path: Path):
    with pytest.raises(KnhanesDataValidationError, match="missing training columns"):
        make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df.drop(columns=missing_var))


@pytest.mark.parametrize("invalid_label", [2.0, np.nan])
def test_preprocess_labeled_rejects_invalid_label(labeled_knhanes_sample_df, invalid_label, tmp_path: Path):
    labeled_knhanes_sample_df[DISEASE_LABEL_VAR] = labeled_knhanes_sample_df[DISEASE_LABEL_VAR].astype(float)
    labeled_knhanes_sample_df.loc[0, DISEASE_LABEL_VAR] = invalid_label

    with pytest.raises(KnhanesDataValidationError, match="must be 0 or 1"):
        make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)


def test_preprocess_labeled_rejects_minor(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[0, "age"] = 18.0

    with pytest.raises(KnhanesDataValidationError, match="only contain adults"):
        make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)


def test_preprocess_labeled_rejects_empty_data(labeled_knhanes_sample_df, tmp_path: Path):
    with pytest.raises(KnhanesDataValidationError, match="no rows"):
        make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df.iloc[0:0])


def test_diabetes_training_excludes_rows_without_any_blood_value(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[1, BLOOD_INPUT_VARS] = np.nan

    df = make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)

    assert df["ID"].tolist() == ["A1", "A3"]
    assert df["나이"].tolist() == [45.0, 60.0]


def test_diabetes_training_keeps_rows_with_partial_blood_values(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[1, BLOOD_INPUT_VARS[1:]] = np.nan

    df = make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)

    assert df["ID"].tolist() == ["A1", "A2", "A3"]


def test_hypertension_training_keeps_rows_without_blood_values(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df.loc[1, BLOOD_INPUT_VARS] = np.nan

    df = make_preprocessor(H, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)

    assert df["ID"].tolist() == ["A1", "A2", "A3"]


def test_inference_keeps_rows_without_blood_values(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df[BLOOD_INPUT_VARS] = np.nan

    processed_df = make_preprocessor(D, tmp_path).preprocess(labeled_knhanes_sample_df)

    assert len(processed_df) == 3


def test_diabetes_training_rejects_data_without_blood_values(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_knhanes_sample_df[BLOOD_INPUT_VARS] = np.nan

    with pytest.raises(KnhanesDataValidationError, match="no rows have blood test values"):
        make_preprocessor(D, tmp_path).preprocess_labeled(labeled_knhanes_sample_df)


def test_run_knhanes_preprocessing_saves_outputs(labeled_knhanes_sample_df, tmp_path: Path):
    labeled_dir = tmp_path / "labeled"
    labeled_dir.mkdir()
    for model_type in ModelType:
        labeled_knhanes_sample_df.to_parquet(labeled_dir / f"{model_type}.parquet", index=False)
    preprocessed_dir = tmp_path / "preprocessed"

    results = run_knhanes_preprocessing(labeled_dir, preprocessed_dir)

    assert set(results) == set(ModelType)
    for model_type, preprocessed_df in results.items():
        saved_df = pd.read_parquet(preprocessed_dir / f"{model_type}.parquet")
        assert saved_df.columns.tolist() == preprocessed_df.columns.tolist()
        assert len(saved_df) == len(preprocessed_df)


def test_run_knhanes_preprocessing_requires_labeled_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Labeled KNHANES data"):
        run_knhanes_preprocessing(tmp_path, tmp_path / "preprocessed")


@pytest.mark.skipif(
    not all((REAL_LABELED_DATA_DIR / f"{model_type}.parquet").exists() for model_type in ModelType),
    reason="Labeled KNHANES data is not available",
)
def test_real_data_keeps_labeled_rows_and_excludes_forbidden_inputs(tmp_path: Path):
    results = run_knhanes_preprocessing(preprocessed_data_dir=tmp_path)

    expected_counts = {D: (27_249, 4_555), H: (28_397, 10_016)}
    for model_type, preprocessed_df in results.items():
        rows, positives = expected_counts[model_type]
        feature_columns = preprocessed_df.columns.difference([*TRAINING_META_VARS, DISEASE_LABEL_VAR])

        assert len(preprocessed_df) == rows
        assert preprocessed_df[DISEASE_LABEL_VAR].sum() == positives
        assert forbidden_columns(model_type).isdisjoint(feature_columns)
        assert preprocessed_df["성별"].notna().all()
