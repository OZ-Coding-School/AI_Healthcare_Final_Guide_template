import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import settings
from src.components.data_splitter import (
    EARLY_TRAIN_GROUP,
    TEST_GROUP,
    TRAIN_GROUP,
    VALIDATION_GROUP,
    KnhanesYearGroupSplitter,
)
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.enums import KnhanesTrainSet, ModelType
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.knhanes_preprocessing_configs import TRAINING_META_VARS
from src.pipelines.knhanes_data_pipeline import run_knhanes_split

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK
REAL_PREPROCESSED_DIR = settings.DATA_DIR / "interim" / "preprocessed"


def make_df() -> pd.DataFrame:
    rows = []
    for year in [2020, 2021, 2022, 2023, 2024]:
        for household in range(40):
            for member in range(2):
                rows.append(
                    {
                        "ID": f"{year}-{household}-{member}",
                        "ID_fam": f"{year}-{household}",
                        "year": year,
                        "wt_itvex": 1.0,
                        "wt_tot": 1.0,
                        "kstrata": 1,
                        "psu": 1,
                        DISEASE_LABEL_VAR: int(household % 4 == 0),
                        "AST": 20.0,
                        "ALT": 30.0,
                        "중성지방": 100.0,
                    }
                )
    return pd.DataFrame(rows)


def test_groups_follow_year_and_keep_households_together():
    df = make_df()

    groups = KnhanesYearGroupSplitter().assign_groups(df)

    assert set(groups[df["year"].isin([2020, 2021])]) == {EARLY_TRAIN_GROUP}
    assert set(groups[df["year"].isin([2022, 2023])]) == {TRAIN_GROUP, VALIDATION_GROUP}
    assert set(groups[df["year"].eq(2024)]) == {TEST_GROUP}
    assert groups.groupby(df["ID_fam"]).nunique().eq(1).all()
    assert groups.eq(VALIDATION_GROUP).sum() == pytest.approx(groups.isin([TRAIN_GROUP, VALIDATION_GROUP]).sum() / 4)


def test_same_seed_gives_same_groups_regardless_of_row_order():
    df = make_df()
    shuffled = df.sample(frac=1, random_state=7)

    groups = KnhanesYearGroupSplitter().assign_groups(df)
    shuffled_groups = KnhanesYearGroupSplitter().assign_groups(shuffled)

    assert groups.to_dict() == shuffled_groups.to_dict()


def test_train_sets_share_validation_and_test_rows():
    df = make_df()
    splitter = KnhanesYearGroupSplitter()
    groups = splitter.assign_groups(df)

    train_a = splitter.split(df, groups, KnhanesTrainSet.TRAIN_A)
    train_b = splitter.split(df, groups, KnhanesTrainSet.TRAIN_B)

    assert set(train_a.meta_train["year"]) == {2020, 2021, 2022, 2023}
    assert set(train_b.meta_train["year"]) == {2022, 2023}
    assert set(train_b.meta_train["ID"]) < set(train_a.meta_train["ID"])
    pd.testing.assert_frame_equal(train_a.meta_validation, train_b.meta_validation)
    pd.testing.assert_frame_equal(train_a.meta_test, train_b.meta_test)
    assert set(train_a.meta_test["year"]) == {2024}


def test_meta_and_label_are_removed_from_features():
    df = make_df()
    splitter = KnhanesYearGroupSplitter()

    split_data = splitter.split(df, splitter.assign_groups(df), KnhanesTrainSet.TRAIN_A)

    for features in [split_data.X_train, split_data.X_validation, split_data.X_test]:
        assert list(features.columns) == ["AST", "ALT", "중성지방"]
    assert split_data.y_train.name == DISEASE_LABEL_VAR
    assert list(split_data.meta_train.columns) == TRAINING_META_VARS
    assert len(split_data.X_test) == len(split_data.y_test) == len(split_data.meta_test)


def test_summarize_reports_each_split():
    df = make_df()
    splitter = KnhanesYearGroupSplitter()

    summary = splitter.summarize(splitter.split(df, splitter.assign_groups(df), KnhanesTrainSet.TRAIN_B))

    assert set(summary) == {"train", "validation", "test"}
    assert summary["test"] == {
        "rows": 80,
        "households": 40,
        "positive": 20,
        "positive_rate": 0.25,
        "years": [2024],
    }


@pytest.mark.parametrize("column", ["ID", "ID_fam", "year", "wt_itvex", DISEASE_LABEL_VAR])
def test_missing_column_raises(column: str):
    with pytest.raises(KnhanesDataValidationError, match="Missing split columns"):
        KnhanesYearGroupSplitter().assign_groups(make_df().drop(columns=[column]))


@pytest.mark.parametrize("column", ["ID", "ID_fam", DISEASE_LABEL_VAR])
def test_missing_split_value_raises(column: str):
    df = make_df()
    df[column] = df[column].astype(object)
    df.loc[0, column] = None

    with pytest.raises(KnhanesDataValidationError, match="missing values"):
        KnhanesYearGroupSplitter().assign_groups(df)


def test_duplicate_id_raises():
    df = make_df()
    df.loc[1, "ID"] = df.loc[0, "ID"]

    with pytest.raises(KnhanesDataValidationError, match="must be unique"):
        KnhanesYearGroupSplitter().assign_groups(df)


def test_missing_year_data_raises():
    df = make_df()

    with pytest.raises(KnhanesDataValidationError, match="Split years"):
        KnhanesYearGroupSplitter().assign_groups(df[df["year"].ne(2024)])


def test_household_shared_with_test_year_raises():
    df = make_df()
    df.loc[df["year"].eq(2024), "ID_fam"] = df.loc[df["year"].eq(2023), "ID_fam"].to_numpy()

    with pytest.raises(KnhanesDataValidationError, match="Households across split groups"):
        KnhanesYearGroupSplitter().assign_groups(df)


def test_invalid_fold_count_raises():
    with pytest.raises(ValueError, match="validation_folds"):
        KnhanesYearGroupSplitter(validation_folds=1)


def test_run_knhanes_split_saves_outputs(tmp_path: Path):
    preprocessed_dir = tmp_path / "preprocessed"
    preprocessed_dir.mkdir()
    base = make_df()
    base.to_parquet(preprocessed_dir / f"{D}.parquet", index=False)
    base.assign(당화혈색소=5.5).to_parquet(preprocessed_dir / f"{H}.parquet", index=False)
    split_dir = tmp_path / "split"
    report_path = tmp_path / "reports" / "split.json"

    results = run_knhanes_split(preprocessed_dir, split_dir, report_path)

    assert set(results) == set(ModelType)
    for model_type in ModelType:
        for train_set in KnhanesTrainSet:
            output_dir = split_dir / model_type / train_set
            for name in ["X", "y", "meta"]:
                for split_name in ["train", "validation", "test"]:
                    assert (output_dir / f"{name}_{split_name}.parquet").exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report[D][KnhanesTrainSet.TRAIN_B]["harmonization_rules"] == []
    assert len(report[H][KnhanesTrainSet.TRAIN_A_TG]["harmonization_rules"]) == 4


def test_run_knhanes_split_requires_preprocessed_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Preprocessed KNHANES data"):
        run_knhanes_split(tmp_path, tmp_path / "split", tmp_path / "split.json")


@pytest.mark.skipif(
    not all((REAL_PREPROCESSED_DIR / f"{model_type}.parquet").exists() for model_type in ModelType),
    reason="Preprocessed KNHANES data is not available",
)
def test_real_data_matches_designed_split(tmp_path: Path):
    results = run_knhanes_split(split_data_dir=tmp_path / "split", split_report_path=tmp_path / "split.json")

    expected_positive = {D: 4_555, H: 10_016}
    expected_rows = {D: 27_249, H: 28_397}
    expected_test = {D: 5_649, H: 5_959}
    for model_type in ModelType:
        train_a = results[model_type][KnhanesTrainSet.TRAIN_A]
        train_b = results[model_type][KnhanesTrainSet.TRAIN_B]
        all_rows = len(train_a.y_train) + len(train_a.y_validation) + len(train_a.y_test)
        all_positive = train_a.y_train.sum() + train_a.y_validation.sum() + train_a.y_test.sum()
        assert all_rows == expected_rows[model_type]
        assert all_positive == expected_positive[model_type]
        assert len(train_a.y_test) == expected_test[model_type]
        assert (
            len(train_b.y_train) + len(train_b.y_validation)
            == expected_rows[model_type]
            - len(train_a.meta_train[train_a.meta_train["year"].isin([2020, 2021])])
            - expected_test[model_type]
        )
        assert np.isin(train_a.meta_test["year"], [2024]).all()
        households = [
            set(train_a.meta_train["ID_fam"]),
            set(train_a.meta_validation["ID_fam"]),
            set(train_a.meta_test["ID_fam"]),
        ]
        assert not households[0] & households[1]
        assert not households[0] & households[2]
        assert not households[1] & households[2]
