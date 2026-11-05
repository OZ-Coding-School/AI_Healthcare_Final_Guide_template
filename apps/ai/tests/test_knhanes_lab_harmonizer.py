import pandas as pd
import pytest

from src.components.knhanes_lab_harmonizer import KnhanesLabHarmonizer
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.enums import KnhanesTrainSet, ModelType
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.knhanes_split_configs import KNHANES_TRAIN_SET_RULES_MAP

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK


def make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": [2021, 2022, 2024],
            DISEASE_LABEL_VAR: [0, 1, 1],
            "AST": [20.0, 20.0, None],
            "ALT": [30.0, 30.0, 30.0],
            "중성지방": [100.0, 100.0, 100.0],
            "당화혈색소": [6.5, 6.4, 6.3],
            "HDL-콜레스테롤": [50.0, 50.0, 50.0],
        }
    )


def test_train_a_applies_guide_formulas_only_after_2021():
    result = KnhanesLabHarmonizer(H).transform(make_df(), KNHANES_TRAIN_SET_RULES_MAP[KnhanesTrainSet.TRAIN_A])

    assert result["AST"].tolist()[:2] == pytest.approx([20.0, 1.057 * 20 + 1.8490])
    assert pd.isna(result.loc[2, "AST"])
    assert result["ALT"].tolist() == pytest.approx([30.0, 1.091 * 30 - 0.6364, 1.091 * 30 - 0.6364])
    assert result["당화혈색소"].tolist() == pytest.approx([6.5, 1.034 * 6.4 - 0.0448, 1.034 * 6.3 - 0.0448])
    assert result["중성지방"].tolist() == [100.0, 100.0, 100.0]


def test_train_a_tg_also_converts_triglyceride_before_2022():
    result = KnhanesLabHarmonizer(H).transform(make_df(), KNHANES_TRAIN_SET_RULES_MAP[KnhanesTrainSet.TRAIN_A_TG])

    assert result["중성지방"].tolist() == pytest.approx([0.99 * 100 + 11.94, 100.0, 100.0])


def test_train_b_keeps_all_values():
    df = make_df()

    result = KnhanesLabHarmonizer(H).transform(df, KNHANES_TRAIN_SET_RULES_MAP[KnhanesTrainSet.TRAIN_B])

    pd.testing.assert_frame_equal(result, df)


@pytest.mark.parametrize("train_set", list(KnhanesTrainSet))
def test_labels_hdl_and_source_data_are_unchanged(train_set: KnhanesTrainSet):
    df = make_df()
    original = df.copy()

    result = KnhanesLabHarmonizer(H).transform(df, KNHANES_TRAIN_SET_RULES_MAP[train_set])

    pd.testing.assert_frame_equal(df, original)
    pd.testing.assert_series_equal(result[DISEASE_LABEL_VAR], original[DISEASE_LABEL_VAR])
    pd.testing.assert_series_equal(result["HDL-콜레스테롤"], original["HDL-콜레스테롤"])


def test_diabetes_model_skips_hba1c_because_it_is_not_an_input():
    df = make_df().drop(columns=["당화혈색소"])

    result = KnhanesLabHarmonizer(D).transform(df, KNHANES_TRAIN_SET_RULES_MAP[KnhanesTrainSet.TRAIN_A])

    assert "당화혈색소" not in result.columns
    assert result.loc[1, "AST"] == pytest.approx(1.057 * 20 + 1.8490)


def test_missing_input_lab_raises():
    with pytest.raises(KnhanesDataValidationError, match="missing lab columns"):
        KnhanesLabHarmonizer(H).transform(
            make_df().drop(columns=["AST"]),
            KNHANES_TRAIN_SET_RULES_MAP[KnhanesTrainSet.TRAIN_A],
        )


def test_non_numeric_lab_raises():
    df = make_df().astype({"ALT": "object"})
    df["ALT"] = "high"

    with pytest.raises(KnhanesDataValidationError, match="must be numeric"):
        KnhanesLabHarmonizer(H).transform(df, KNHANES_TRAIN_SET_RULES_MAP[KnhanesTrainSet.TRAIN_A])


def test_missing_year_raises():
    df = make_df()
    df["year"] = df["year"].astype(float)
    df.loc[0, "year"] = None

    with pytest.raises(KnhanesDataValidationError, match="year is required"):
        KnhanesLabHarmonizer(H).transform(df, [])
