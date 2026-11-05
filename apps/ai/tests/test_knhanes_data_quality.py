"""
KNHANES 데이터 파이프라인의 최종 산출물을 단계 구분 없이 검증합니다.

같은 검증을 합성 데이터로 항상 실행하고, 실제 데이터가 있으면 저장된 산출물에도 실행합니다.
라벨 기준값은 설정을 가져오지 않고 직접 적어 설정이 바뀌면 테스트가 실패하게 합니다.
Test 분할은 라벨과 구성만 확인하며, 성능이나 피처와 라벨의 관계는 Train에서만 측정합니다.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from src.enums import KnhanesTrainSet, ModelType
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.knhanes_preprocessing_configs import (
    KNHANES_VARIABLES_CONFIG_MAP,
    MODEL_FORBIDDEN_INPUT_VARS_MAP,
    MODEL_INPUT_VARS_MAP,
    TRAINING_META_VARS,
)
from src.knhanes_split_configs import KNHANES_TRAIN_SET_RULES_MAP
from src.pipelines.knhanes_data_pipeline import (
    MERGED_DATA_PATH,
    PREPROCESSED_DATA_DIR,
    SPLIT_DATA_DIR,
    run_knhanes_labeling,
    run_knhanes_preprocessing,
    run_knhanes_split,
)

D = ModelType.DIABETES_RISK
H = ModelType.HYPERTENSION_RISK

SPLIT_NAMES = ["train", "validation", "test"]
EARLY_YEARS = {2020, 2021}
DEVELOPMENT_YEARS = {2022, 2023}
TEST_YEARS = {2024}
HOUSEHOLDS_PER_YEAR = 28

LABEL_BY_VAR_NAME = {var["name"]: str(var["label"]) for var in KNHANES_VARIABLES_CONFIG_MAP}
DERIVED_INPUT_COLUMN_MAP = {D: "당뇨병 가족력 보유 여부", H: "고혈압 가족력 보유 여부"}

# 어떤 입력 하나로 라벨을 거의 맞히면 라벨 원천이 입력에 섞였을 가능성이 높습니다.
MAX_SINGLE_INPUT_AUC = 0.95

# 결측이 이 비율 이상 한쪽 라벨에만 있으면 값이 아니라 결측 여부로 라벨이 드러납니다.
MAX_POSITIVE_RATE_WHEN_MISSING = 0.95
MIN_MISSING_ROWS = 30

SCENARIOS: list[dict[str, Any]] = [
    {},
    {"HE_glu": 126.0},
    {"HE_glu": 125.0},
    {"HE_HbA1c": 6.5},
    {"HE_HbA1c": 6.4},
    {"DE1_dg": 1.0},
    {"DE1_31": 1.0},
    {"DE1_32": 1.0},
    {"HE_sbp": 140.0},
    {"HE_dbp": 90.0},
    {"DI1_2": 1.0},
    {"DI1_pr": 1.0},
    {"HE_glu": 200.0, "HE_fst": 7.0},
    {"HE_prg": 1.0},
    {"HE_dprg": 5.0},
    {"age": 18.0},
    {"DE1_dg": 9.0},
    {"DI1_pr": 9.0},
    {"HE_sbp": np.nan},
    {"HE_HbA1c": np.nan},
]


@dataclass(frozen=True)
class KnhanesArtifacts:
    merged_path: Path
    preprocessed_dir: Path
    split_dir: Path


@dataclass(frozen=True)
class SavedSplit:
    X: dict[str, pd.DataFrame]
    y: dict[str, pd.Series]
    meta: dict[str, pd.DataFrame]

    def all_meta(self) -> pd.DataFrame:
        return pd.concat(self.meta.values(), ignore_index=True)

    def labels_by_id(self) -> pd.Series:
        ids = self.all_meta()["ID"]
        labels = pd.concat(self.y.values(), ignore_index=True)
        return pd.Series(labels.to_numpy(), index=ids.to_numpy()).sort_index()


def make_row(row_number: int, year: int, household: int, member: int, **overrides: Any) -> dict[str, Any]:
    """두 질환 모두 음성인 성인 1명입니다. 행마다 수치가 달라야 행이 섞였을 때 드러납니다."""
    return {
        "ID": f"A{row_number}",
        "ID_fam": f"F{year}{household}",
        "year": year,
        "wt_itvex": 1000.0,
        "wt_tot": 1000.0,
        "kstrata": 1.0,
        "psu": 1.0,
        "sex": float(member % 2 + 1),
        "age": 30.0 + row_number % 40,
        "HE_ht": 170.0,
        "HE_wt": 70.0,
        "HE_wc": 70.0 + row_number * 0.01,
        "HE_BMI": 24.0,
        "BD1": 2.0,
        "BD1_11": 3.0,
        "BD2_1": 2.0,
        "BS3_1": 8.0,
        "BS3_2": 888.0,
        "HE_chol": 180.0,
        "HE_HDL_st2": 50.0,
        "HE_TG": 100.0 + row_number * 0.1,
        "HE_ast": 20.0 + row_number * 0.01,
        "HE_alt": 25.0 + row_number * 0.01,
        "HE_crea": 0.9,
        "HE_Upro": 0.0,
        "HE_Uglu": 0.0,
        "DE1_dg": 0.0,
        "DE1_pr": 8.0,
        "DE1_31": 8.0,
        "DE1_32": 8.0,
        "DI1_pr": 8.0,
        "DI1_2": 8.0,
        "HE_glu": 90.0,
        "HE_fst": 12.0,
        "HE_HbA1c": 5.0 + row_number % 10 * 0.01,
        "HE_sbp": 110.0,
        "HE_dbp": 70.0,
        "HE_DM_HbA1c": 1.0,
        "HE_HP": 1.0,
        "HE_prg": 0.0,
        "HE_dprg": np.nan,
        "HE_DMfh1": 0.0,
        "HE_DMfh2": 0.0,
        "HE_DMfh3": 8.0,
        "HE_HPfh1": 0.0,
        "HE_HPfh2": 0.0,
        "HE_HPfh3": 8.0,
    } | overrides


def make_merged_df() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in sorted(EARLY_YEARS | DEVELOPMENT_YEARS | TEST_YEARS):
        for household in range(HOUSEHOLDS_PER_YEAR):
            scenario = SCENARIOS[household % len(SCENARIOS)]
            rows.append(make_row(len(rows), year, household, 0, **scenario))
            rows.append(make_row(len(rows), year, household, 1))
    return pd.DataFrame(rows)


def load_split(artifacts: KnhanesArtifacts, model_type: ModelType, train_set: KnhanesTrainSet) -> SavedSplit:
    split_dir = artifacts.split_dir / model_type / train_set
    return SavedSplit(
        X={name: pd.read_parquet(split_dir / f"X_{name}.parquet") for name in SPLIT_NAMES},
        y={name: pd.read_parquet(split_dir / f"y_{name}.parquet")[DISEASE_LABEL_VAR] for name in SPLIT_NAMES},
        meta={name: pd.read_parquet(split_dir / f"meta_{name}.parquet") for name in SPLIT_NAMES},
    )


def expected_labels(merged_df: pd.DataFrame, model_type: ModelType) -> pd.Series:
    """파이프라인 코드를 쓰지 않고 B안 라벨을 다시 계산합니다. 판정할 수 없는 행은 결과에 없습니다."""
    adults = merged_df[merged_df["age"].ge(19) & ~merged_df["HE_prg"].eq(1) & merged_df["HE_dprg"].isna()]

    if model_type == D:
        fasting_glucose = adults["HE_glu"].where(adults["HE_fst"].ge(8))
        positive = (
            adults["DE1_dg"].eq(1)
            | adults["DE1_31"].eq(1)
            | adults["DE1_32"].eq(1)
            | fasting_glucose.ge(126)
            | adults["HE_HbA1c"].ge(6.5)
        )
        measured = fasting_glucose.notna() & adults["HE_HbA1c"].notna()
        responses = adults[["DE1_dg", "DE1_31", "DE1_32"]]
    else:
        positive = (
            adults["HE_sbp"].ge(140)
            | adults["HE_dbp"].ge(90)
            | adults["DI1_2"].isin([1, 2, 3, 4])
            | adults["DI1_pr"].eq(1)
        )
        measured = adults["HE_sbp"].notna() & adults["HE_dbp"].notna()
        responses = adults[["DI1_pr", "DI1_2"]]

    answered = responses.notna().all(axis=1) & responses.ne(9).all(axis=1)
    labelable = positive | (measured & answered)
    return pd.Series(positive[labelable].astype(int).to_numpy(), index=adults.loc[labelable, "ID"]).sort_index()


def expected_features(
    artifacts: KnhanesArtifacts,
    model_type: ModelType,
    train_set: KnhanesTrainSet,
    X: pd.DataFrame,
    meta: pd.DataFrame,
) -> pd.DataFrame:
    """전처리 결과를 ID로 찾아 전환식을 적용합니다. 저장된 X와 같은 행 순서로 반환합니다."""
    preprocessed_df = pd.read_parquet(artifacts.preprocessed_dir / f"{model_type}.parquet")
    expected = preprocessed_df.set_index("ID").loc[meta["ID"], X.columns].reset_index(drop=True)

    for rule in KNHANES_TRAIN_SET_RULES_MAP[train_set]:
        if rule.var_name not in MODEL_INPUT_VARS_MAP[model_type]:
            continue
        column = LABEL_BY_VAR_NAME[rule.var_name]
        target_rows = meta["year"].isin(rule.years).to_numpy()
        expected[column] = expected[column].astype(float)
        expected.loc[target_rows, column] = expected.loc[target_rows, column] * rule.slope + rule.intercept

    return expected


def with_plain_categories(df: pd.DataFrame) -> pd.DataFrame:
    categorical_columns = df.select_dtypes("category").columns
    return df.astype({column: object for column in categorical_columns})


@pytest.fixture(scope="module")
def synthetic_artifacts(tmp_path_factory: pytest.TempPathFactory) -> KnhanesArtifacts:
    root = tmp_path_factory.mktemp("knhanes_quality")
    artifacts = KnhanesArtifacts(root / "merged.parquet", root / "preprocessed", root / "split")
    labeled_dir = root / "labeled"

    make_merged_df().to_parquet(artifacts.merged_path, index=False)
    # 공식 분류 대조는 라벨 생성기 테스트에서 검증하므로 합성 데이터에서는 끕니다.
    run_knhanes_labeling(
        artifacts.merged_path,
        labeled_dir,
        root / "label.json",
        strict_official_match=False,
    )
    run_knhanes_preprocessing(labeled_dir, artifacts.preprocessed_dir)
    run_knhanes_split(artifacts.preprocessed_dir, artifacts.split_dir, root / "split.json")
    return artifacts


@pytest.fixture(scope="module")
def real_artifacts() -> KnhanesArtifacts:
    required_paths = [
        MERGED_DATA_PATH,
        *(PREPROCESSED_DATA_DIR / f"{model_type}.parquet" for model_type in ModelType),
        *(
            SPLIT_DATA_DIR / model_type / train_set / "meta_test.parquet"
            for model_type in ModelType
            for train_set in KnhanesTrainSet
        ),
    ]
    if not all(path.exists() for path in required_paths):
        pytest.skip("KNHANES pipeline outputs are not available")
    return KnhanesArtifacts(MERGED_DATA_PATH, PREPROCESSED_DATA_DIR, SPLIT_DATA_DIR)


@pytest.fixture(scope="module", params=["synthetic", "real"])
def artifacts(request: pytest.FixtureRequest) -> KnhanesArtifacts:
    return request.getfixturevalue(f"{request.param}_artifacts")


@pytest.mark.parametrize("model_type", list(ModelType))
@pytest.mark.parametrize("train_set", list(KnhanesTrainSet))
def test_saved_labels_match_independent_rules(
    artifacts: KnhanesArtifacts,
    model_type: ModelType,
    train_set: KnhanesTrainSet,
):
    merged_df = pd.read_parquet(artifacts.merged_path)
    expected = expected_labels(merged_df, model_type)
    if train_set not in (KnhanesTrainSet.TRAIN_A, KnhanesTrainSet.TRAIN_A_TG):
        early_ids = merged_df.loc[merged_df["year"].isin(EARLY_YEARS), "ID"]
        expected = expected[~expected.index.isin(early_ids)]

    labels = load_split(artifacts, model_type, train_set).labels_by_id()

    pd.testing.assert_series_equal(labels, expected, check_names=False, check_dtype=False, check_index_type=False)


@pytest.mark.parametrize("model_type", list(ModelType))
def test_saved_rows_are_adults_and_not_pregnant(artifacts: KnhanesArtifacts, model_type: ModelType):
    merged_df = pd.read_parquet(artifacts.merged_path)
    saved_ids = load_split(artifacts, model_type, KnhanesTrainSet.TRAIN_A).all_meta()["ID"]

    saved_rows = merged_df[merged_df["ID"].isin(saved_ids)]

    assert len(saved_rows) == len(saved_ids)
    assert saved_rows["age"].ge(19).all()
    assert not saved_rows["HE_prg"].eq(1).any()
    assert saved_rows["HE_dprg"].isna().all()


@pytest.mark.parametrize("model_type", list(ModelType))
@pytest.mark.parametrize("train_set", list(KnhanesTrainSet))
def test_saved_features_are_exactly_the_allowed_inputs(
    artifacts: KnhanesArtifacts,
    model_type: ModelType,
    train_set: KnhanesTrainSet,
):
    allowed_columns = {LABEL_BY_VAR_NAME[name] for name in MODEL_INPUT_VARS_MAP[model_type]}
    allowed_columns.add(DERIVED_INPUT_COLUMN_MAP[model_type])
    forbidden_names = set(MODEL_FORBIDDEN_INPUT_VARS_MAP[model_type])
    forbidden_columns = forbidden_names | {LABEL_BY_VAR_NAME.get(name, name) for name in forbidden_names}
    forbidden_columns.add(DISEASE_LABEL_VAR)

    split_data = load_split(artifacts, model_type, train_set)

    for name in SPLIT_NAMES:
        columns = set(split_data.X[name].columns)
        assert columns == allowed_columns
        assert columns.isdisjoint(forbidden_columns)
        assert split_data.X[name].columns.tolist() == split_data.X["train"].columns.tolist()


@pytest.mark.parametrize("model_type", list(ModelType))
@pytest.mark.parametrize("train_set", list(KnhanesTrainSet))
def test_saved_features_stay_aligned_with_meta_after_harmonization(
    artifacts: KnhanesArtifacts,
    model_type: ModelType,
    train_set: KnhanesTrainSet,
):
    split_data = load_split(artifacts, model_type, train_set)

    for name in SPLIT_NAMES:
        X, meta = split_data.X[name], split_data.meta[name]
        assert len(X) == len(split_data.y[name]) == len(meta)
        expected = expected_features(artifacts, model_type, train_set, X, meta)
        pd.testing.assert_frame_equal(with_plain_categories(X), with_plain_categories(expected), check_dtype=False)


@pytest.mark.parametrize("model_type", list(ModelType))
@pytest.mark.parametrize("train_set", list(KnhanesTrainSet))
def test_saved_splits_do_not_share_people_or_households(
    artifacts: KnhanesArtifacts,
    model_type: ModelType,
    train_set: KnhanesTrainSet,
):
    meta = load_split(artifacts, model_type, train_set).meta

    for column in ["ID", "ID_fam"]:
        train_values = set(meta["train"][column])
        validation_values = set(meta["validation"][column])
        test_values = set(meta["test"][column])
        assert train_values.isdisjoint(validation_values)
        assert train_values.isdisjoint(test_values)
        assert validation_values.isdisjoint(test_values)
    assert not pd.concat(meta.values())["ID"].duplicated().any()


@pytest.mark.parametrize("model_type", list(ModelType))
@pytest.mark.parametrize(
    ("train_set", "train_years"),
    [
        (KnhanesTrainSet.TRAIN_A, EARLY_YEARS | DEVELOPMENT_YEARS),
        (KnhanesTrainSet.TRAIN_A_TG, EARLY_YEARS | DEVELOPMENT_YEARS),
        (KnhanesTrainSet.TRAIN_B, DEVELOPMENT_YEARS),
    ],
)
def test_saved_splits_use_designed_years(
    artifacts: KnhanesArtifacts,
    model_type: ModelType,
    train_set: KnhanesTrainSet,
    train_years: set[int],
):
    meta = load_split(artifacts, model_type, train_set).meta

    assert set(meta["train"]["year"].astype(int)) == train_years
    assert set(meta["validation"]["year"].astype(int)) == DEVELOPMENT_YEARS
    assert set(meta["test"]["year"].astype(int)) == TEST_YEARS


@pytest.mark.parametrize("model_type", list(ModelType))
def test_train_sets_are_compared_on_the_same_people(artifacts: KnhanesArtifacts, model_type: ModelType):
    train_a = load_split(artifacts, model_type, KnhanesTrainSet.TRAIN_A)
    train_a_tg = load_split(artifacts, model_type, KnhanesTrainSet.TRAIN_A_TG)
    train_b = load_split(artifacts, model_type, KnhanesTrainSet.TRAIN_B)

    for name in ["validation", "test"]:
        pd.testing.assert_frame_equal(train_a.meta[name], train_a_tg.meta[name])
        pd.testing.assert_frame_equal(train_a.meta[name], train_b.meta[name])
        pd.testing.assert_series_equal(train_a.y[name], train_b.y[name])

    development_rows = train_a.meta["train"]["year"].isin(DEVELOPMENT_YEARS)
    assert set(train_a.meta["train"].loc[development_rows, "ID"]) == set(train_b.meta["train"]["ID"])


def test_saved_meta_keeps_only_split_and_survey_columns(artifacts: KnhanesArtifacts):
    for model_type in ModelType:
        meta = load_split(artifacts, model_type, KnhanesTrainSet.TRAIN_A).meta
        assert all(frame.columns.tolist() == TRAINING_META_VARS for frame in meta.values())


@pytest.mark.parametrize("model_type", list(ModelType))
def test_validation_represents_development_years(real_artifacts: KnhanesArtifacts, model_type: ModelType):
    split_data = load_split(real_artifacts, model_type, KnhanesTrainSet.TRAIN_B)
    train_rows = len(split_data.y["train"])
    validation_rows = len(split_data.y["validation"])

    assert validation_rows / (train_rows + validation_rows) == pytest.approx(0.25, abs=0.02)
    assert split_data.y["validation"].mean() == pytest.approx(split_data.y["train"].mean(), abs=0.02)


@pytest.mark.parametrize("model_type", list(ModelType))
def test_no_single_input_nearly_reproduces_label(real_artifacts: KnhanesArtifacts, model_type: ModelType):
    split_data = load_split(real_artifacts, model_type, KnhanesTrainSet.TRAIN_A)
    X, y = split_data.X["train"], split_data.y["train"]

    auc_by_column: dict[str, float] = {}
    for column in X.columns:
        values = X[column]
        if isinstance(values.dtype, pd.CategoricalDtype):
            scores = y.groupby(values.astype(object).fillna("MISSING")).transform("mean")
        else:
            scores = values.fillna(values.median())
        auc = roc_auc_score(y, scores)
        auc_by_column[column] = max(auc, 1 - auc)

    suspicious = {column: auc for column, auc in auc_by_column.items() if auc >= MAX_SINGLE_INPUT_AUC}
    assert suspicious == {}


@pytest.mark.parametrize(
    "model_type",
    [
        pytest.param(
            D,
            marks=pytest.mark.xfail(
                strict=True,
                reason="음성 확정에 혈액검사가 필요해 혈액 지표 결측 행이 양성만 남습니다. 처리 방침 결정 필요",
            ),
        ),
        H,
    ],
)
def test_missing_input_does_not_reveal_label(real_artifacts: KnhanesArtifacts, model_type: ModelType):
    split_data = load_split(real_artifacts, model_type, KnhanesTrainSet.TRAIN_A)
    X, y = split_data.X["train"], split_data.y["train"]

    revealing_columns: dict[str, float] = {}
    for column in X.columns:
        missing = X[column].isna()
        if missing.sum() >= MIN_MISSING_ROWS and y[missing].mean() >= MAX_POSITIVE_RATE_WHEN_MISSING:
            revealing_columns[column] = float(y[missing].mean())

    assert revealing_columns == {}
