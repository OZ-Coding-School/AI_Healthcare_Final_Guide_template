import pytest

from src.enums import ModelType
from src.knhanes_preprocessing_configs import (
    KNHANES_VARIABLES_CONFIG_MAP,
    MODEL_FORBIDDEN_INPUT_VARS_MAP,
    MODEL_INPUT_VARS_MAP,
    MODEL_LABEL_SOURCE_VARS_MAP,
    MODEL_OFFICIAL_LABEL_VAR_MAP,
    MODEL_TARGET_VAR_MAP,
    MODEL_VARIABLES_MAP,
    TRAINING_META_VARS,
)


@pytest.mark.parametrize("model_type", list(ModelType))
def test_input_vars_do_not_include_forbidden_vars(model_type: ModelType):
    overlap = set(MODEL_INPUT_VARS_MAP[model_type]) & set(MODEL_FORBIDDEN_INPUT_VARS_MAP[model_type])

    assert overlap == set()


@pytest.mark.parametrize("model_type", list(ModelType))
def test_forbidden_vars_include_all_label_vars(model_type: ModelType):
    forbidden_vars = set(MODEL_FORBIDDEN_INPUT_VARS_MAP[model_type])

    assert set(MODEL_LABEL_SOURCE_VARS_MAP[model_type]) <= forbidden_vars
    assert set(MODEL_OFFICIAL_LABEL_VAR_MAP.values()) <= forbidden_vars
    assert MODEL_TARGET_VAR_MAP[model_type] in forbidden_vars


@pytest.mark.parametrize("model_type", list(ModelType))
def test_input_vars_are_unique_and_defined(model_type: ModelType):
    input_vars = MODEL_INPUT_VARS_MAP[model_type]
    defined_vars = {var["name"] for var in KNHANES_VARIABLES_CONFIG_MAP}

    assert len(input_vars) == len(set(input_vars))
    assert set(input_vars) <= defined_vars


@pytest.mark.parametrize("model_type", list(ModelType))
def test_training_meta_vars_are_forbidden_inputs(model_type: ModelType):
    assert set(TRAINING_META_VARS) <= set(MODEL_FORBIDDEN_INPUT_VARS_MAP[model_type])


def test_other_disease_status_stays_as_input():
    assert "DI1_pr" in MODEL_INPUT_VARS_MAP[ModelType.DIABETES_RISK]
    assert "DE1_pr" in MODEL_INPUT_VARS_MAP[ModelType.HYPERTENSION_RISK]


@pytest.mark.parametrize("model_type", list(ModelType))
def test_existing_preprocessor_vars_are_preserved(model_type: ModelType):
    expected_vars = MODEL_VARIABLES_MAP["common"] + MODEL_VARIABLES_MAP[model_type]

    assert set(MODEL_INPUT_VARS_MAP[model_type]) | {MODEL_TARGET_VAR_MAP[model_type]} == set(expected_vars)
