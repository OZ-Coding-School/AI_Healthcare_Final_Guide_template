from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.components.data_preprocessor import KnhanesPreprocessor
from src.components.knhanes_inference_errors import InferenceInputError
from src.components.knhanes_input_adapter import drinks_per_session_code, to_knhanes_raw_frame
from src.components.knhanes_service_input import calculate_age, parse_service_input
from src.enums import ModelType
from src.knhanes_preprocessing_configs import MODEL_INPUT_VARS_MAP


def valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "gender": "M",
        "birth_date": "1975-03-02",
        "has_diabetes": False,
        "has_hypertension": False,
        "screening_date": "2026-05-10",
        "height": 172.0,
        "weight": 82.5,
        "waist_circumference": 94.0,
        "sbp": 138,
        "dbp": 88,
        "fbs": 112,
        "hba1c": 6.1,
        "triglyceride": 210,
        "total_cholesterol": 215,
        "hdl": 38,
        "ast": 32,
        "alt": 45,
        "creatinine": 0.95,
        "urine_protein": "-",
        "urine_glucose": "±",
        "diabetes_family_history": {"father": "YES", "mother": "NO", "siblings": "NO"},
        "hypertension_family_history": {"father": "NO", "mother": "UNKNOWN", "siblings": "NO_SIBLINGS"},
        "smoking_status": "CURRENT",
        "cigarettes_per_day": 15,
        "drinking_status": "CURRENT",
        "drinking_frequency": "WEEKLY_2_TO_3",
        "drinks_per_session": 5,
    }
    payload.update(overrides)
    return payload


def raw_row(**overrides: Any) -> dict[str, float]:
    return to_knhanes_raw_frame(parse_service_input(valid_payload(**overrides))).iloc[0].to_dict()


class TestServiceInputValidation:
    def test_valid_payload_passes(self):
        service_input = parse_service_input(valid_payload())
        assert service_input.age == 51

    @pytest.mark.parametrize(
        ("overrides", "field"),
        [
            ({"height": 500.0}, "height"),
            ({"gender": "X"}, "gender"),
            ({"urine_protein": "5+"}, "urine_protein"),
            ({"unknown_field": 1}, "unknown_field"),
            ({"diabetes_family_history": {"father": "NO_SIBLINGS", "mother": "NO", "siblings": "NO"}}, "diabetes"),
        ],
    )
    def test_field_errors_name_the_field(self, overrides, field):
        with pytest.raises(InferenceInputError) as error:
            parse_service_input(valid_payload(**overrides))
        assert any(field in item.field for item in error.value.errors)

    def test_missing_blood_value_is_rejected(self):
        payload = valid_payload()
        del payload["hdl"]
        with pytest.raises(InferenceInputError) as error:
            parse_service_input(payload)
        assert [item.field for item in error.value.errors] == ["hdl"]

    @pytest.mark.parametrize(
        "overrides",
        [
            {"dbp": 140, "sbp": 138},
            {"hdl": 190, "total_cholesterol": 180},
            {"birth_date": "2010-01-01"},
            {"screening_date": (date.today() + timedelta(days=1)).isoformat()},
            {"smoking_status": "NEVER", "cigarettes_per_day": 10},
            {"drinking_status": "NEVER", "drinking_frequency": "WEEKLY_2_TO_3", "drinks_per_session": None},
            {"drinking_status": "CURRENT", "drinking_frequency": "NOT_APPLICABLE"},
            {"drinking_status": "CURRENT", "drinks_per_session": 0},
        ],
    )
    def test_inconsistent_input_is_rejected(self, overrides):
        with pytest.raises(InferenceInputError):
            parse_service_input(valid_payload(**overrides))

    def test_error_message_does_not_contain_input_value(self):
        with pytest.raises(InferenceInputError) as error:
            parse_service_input(valid_payload(height=987.6))
        assert "987.6" not in str(error.value)

    def test_non_mapping_input_is_rejected(self):
        with pytest.raises(InferenceInputError):
            parse_service_input(["not", "a", "mapping"])  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("birth", "on", "expected"),
        [(date(1980, 6, 15), date(2026, 6, 14), 45), (date(1980, 6, 15), date(2026, 6, 15), 46)],
    )
    def test_calculate_age_counts_birthday(self, birth, on, expected):
        assert calculate_age(birth, on) == expected


class TestKnhanesCodeConversion:
    def test_basic_codes(self):
        row = raw_row()
        assert row["sex"] == 1
        assert row["age"] == 51
        assert np.isnan(row["HE_BMI"])
        assert row["HE_Upro"] == 0
        assert row["HE_Uglu"] == 1
        assert row["DE1_pr"] == 0 and row["DI1_pr"] == 0
        assert (row["HE_DMfh1"], row["HE_DMfh2"], row["HE_DMfh3"]) == (1, 0, 0)
        assert (row["HE_HPfh1"], row["HE_HPfh2"], row["HE_HPfh3"]) == (0, 9, 8)

    def test_age_is_top_coded_at_80(self):
        assert raw_row(birth_date="1930-01-01")["age"] == 80

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            ({"smoking_status": "NEVER", "cigarettes_per_day": None}, (8, 888)),
            ({"smoking_status": "FORMER", "cigarettes_per_day": 0}, (3, 888)),
            ({"smoking_status": "CURRENT", "cigarettes_per_day": None}, (1, 999)),
            ({"smoking_status": "CURRENT", "cigarettes_per_day": 20}, (1, 20)),
        ],
    )
    def test_smoking_codes(self, overrides, expected):
        row = raw_row(**overrides)
        assert (row["BS3_1"], row["BS3_2"]) == expected

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            (
                {"drinking_status": "NEVER", "drinking_frequency": "NOT_APPLICABLE", "drinks_per_session": None},
                (1, 8, 8),
            ),
            ({"drinking_status": "FORMER", "drinking_frequency": "NOT_APPLICABLE", "drinks_per_session": 0}, (2, 1, 8)),
            ({"drinking_status": "CURRENT", "drinking_frequency": "LESS_THAN_MONTHLY"}, (2, 2, 3)),
            (
                {"drinking_status": "CURRENT", "drinking_frequency": "WEEKLY_4_OR_MORE", "drinks_per_session": None},
                (2, 6, 9),
            ),
        ],
    )
    def test_drinking_codes(self, overrides, expected):
        row = raw_row(**overrides)
        assert (row["BD1"], row["BD1_11"], row["BD2_1"]) == expected

    @pytest.mark.parametrize(
        ("drinks", "code"),
        [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4), (9, 4), (10, 5), (40, 5)],
    )
    def test_drinks_per_session_bins(self, drinks, code):
        assert drinks_per_session_code(drinks) == code

    def test_drinks_per_session_rejects_zero(self):
        with pytest.raises(ValueError):
            drinks_per_session_code(0)


class TestPreprocessingOfConvertedInput:
    @pytest.mark.parametrize("model_type", list(ModelType))
    def test_converted_input_passes_training_preprocessing(self, model_type, tmp_path: Path):
        raw = to_knhanes_raw_frame(parse_service_input(valid_payload()))
        assert set(MODEL_INPUT_VARS_MAP[model_type]) <= set(raw.columns)

        features = KnhanesPreprocessor(use_case=model_type).preprocess(raw)

        assert len(features) == 1
        assert features["현재 흡연 여부"].iloc[0] == "CURRENT"
        assert features["1년간 음주빈도"].iloc[0] == "WEEKLY_2_TO_3"
        assert features["한 번에 마시는 음주량"].iloc[0] == "5~6잔"
        assert features["BMI"].iloc[0] == pytest.approx(82.5 / 1.72**2)

    def test_never_smoker_has_zero_cigarettes(self):
        raw = to_knhanes_raw_frame(parse_service_input(valid_payload(smoking_status="NEVER", cigarettes_per_day=None)))
        features = KnhanesPreprocessor(use_case=ModelType.DIABETES_RISK).preprocess(raw)
        assert features["현재 흡연 여부"].iloc[0] == "NEVER"
        assert features["하루평균 담배 흡연량"].iloc[0] == 0

    def test_preprocessor_without_output_dir_does_not_save(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        preprocessor = KnhanesPreprocessor(use_case=ModelType.DIABETES_RISK)
        assert preprocessor.output_dir is None
        assert list(tmp_path.iterdir()) == []
        with pytest.raises(ValueError):
            preprocessor.save(preprocessor.preprocess(to_knhanes_raw_frame(parse_service_input(valid_payload()))))
