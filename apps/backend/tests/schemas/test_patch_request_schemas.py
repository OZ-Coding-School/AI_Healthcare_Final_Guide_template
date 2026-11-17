import pytest
from pydantic import ValidationError

from app.schemas.health_profiles import HealthProfileUpdateRequest
from app.schemas.users import UserUpdateRequest


@pytest.mark.parametrize("payload", [{}, {"nickname": None}, {"phone_number": None}])
def test_user_update_requires_a_non_null_field(payload):
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate(payload)


def test_user_update_accepts_a_valid_field():
    request = UserUpdateRequest.model_validate({"nickname": "새 닉네임"})

    assert request.nickname == "새 닉네임"


@pytest.mark.parametrize(
    "payload",
    [{}, {"height": None}, {"has_diabetes": None}, {"has_hypertension": None}],
)
def test_health_profile_update_requires_a_non_null_field(payload):
    with pytest.raises(ValidationError):
        HealthProfileUpdateRequest.model_validate(payload)


def test_health_profile_update_accepts_false_boolean_value():
    request = HealthProfileUpdateRequest.model_validate({"has_diabetes": False})

    assert request.has_diabetes is False
