from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase
from uuid6 import uuid7

from app.core.enums import BloodSugarMeasurementType, ExerciseType
from app.core.utils.jwt.provider import JWTProvider
from app.main import app
from app.models.health_profiles import BloodSugarMeasurement
from app.models.user_models import User


class TestBloodSugarMeasurementAPI(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.test_user = await self._create_test_user()
        self.headers = await self._get_auth_header(self.test_user)
        self.base_url = "http://test"
        self.api_path = "api/v1/blood-sugar-measurements"

    async def _create_test_user(
        self, email: str = "test_blood_sugar@example.com", phone_number: str = "01099991234"
    ) -> User:
        # 테스트용 사용자 생성
        return await User.create(
            email=email,
            hashed_password="hashed_password",
            nickname="혈당테스터",
            name="테스터",
            phone_number=phone_number,
        )

    async def _get_auth_header(self, user: User) -> dict[str, str]:
        token_pair = JWTProvider().issue_jwt_pair(user)
        return {"Authorization": f"Bearer {token_pair['access_token']}"}

    async def test_create_blood_sugar_measurement_success(self) -> None:
        measure_type = BloodSugarMeasurementType.AFTER_LUNCH
        exercise_type = ExerciseType.CARDIO
        payload = {
            "measure_type": measure_type,
            "blood_glucose": 120,
            "minutes_since_meal": 60,
            "has_exercised": True,
            "exercise_type": exercise_type,
            "exercise_minutes": 30,
            "minutes_since_exercise": 10,
            "has_medicated": False,
            "measured_at": datetime.now(UTC).isoformat(),
            "memo": "점심 식후 측정",
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.post(self.api_path, json=payload, headers=self.headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["blood_glucose"] == payload["blood_glucose"]
        assert data["measure_type"] == measure_type.label
        assert data["minutes_since_meal"] == payload["minutes_since_meal"]
        assert data["has_exercised"] is True
        assert data["exercise_type"] == exercise_type.label

    async def test_create_blood_sugar_measurement_normalization_when_has_exercised_is_false(self) -> None:
        # has_exercised가 False인데 운동 관련 필드가 있는 경우 (스키마에서 None으로 정규화되어야 함)
        payload = {
            "measure_type": BloodSugarMeasurementType.FASTING,
            "blood_glucose": 90,
            "has_exercised": False,
            "exercise_type": ExerciseType.CARDIO,  # 무시되어야 함
            "exercise_minutes": 30,  # 무시되어야 함
            "minutes_since_exercise": 100,  # 무시되어야 함
            "has_medicated": True,
            "medicine_name": "Metformin",
            "minutes_since_medication": 120,
            "measured_at": datetime.now(UTC).isoformat(),
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.post(self.api_path, json=payload, headers=self.headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["has_exercised"] is False
        assert data["exercise_type"] is None
        assert data["exercise_minutes"] is None
        assert data["minutes_since_exercise"] is None
        assert data["medicine_name"] == "Metformin"

    async def test_create_blood_sugar_measurement_normalization_when_has_medicated_is_false(self) -> None:
        # has_medicated가 False인데 복약 관련 필드 데이터가 넘어온 경우 (스키마에서 None으로 정규화되어야 함)
        payload = {
            "measure_type": BloodSugarMeasurementType.FASTING,
            "blood_glucose": 90,
            "has_exercised": True,
            "exercise_type": ExerciseType.CARDIO,
            "exercise_minutes": 30,
            "minutes_since_exercise": 100,
            "has_medicated": False,
            "medicine_name": "Metformin",  # 무시되어야 함
            "minutes_since_medication": 120,  # 무시되어야 함
            "measured_at": datetime.now(UTC).isoformat(),
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.post(self.api_path, json=payload, headers=self.headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["has_medicated"] is False
        assert data["medicine_name"] is None
        assert data["minutes_since_medication"] is None

    async def test_create_blood_sugar_measurement_invalid_data(self) -> None:
        payload = {
            "measure_type": "INVALID_TYPE",
            "blood_glucose": 90,
            "has_exercised": True,
            "exercise_type": "INVALID_TYPE",
            "exercise_minutes": 30,
            "minutes_since_exercise": 100,
            "has_medicated": False,
            "medicine_name": "Metformin",  # 무시되어야 함
            "minutes_since_medication": 120,  # 무시되어야 함
            "measured_at": datetime.now(UTC).isoformat(),
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.post(self.api_path, json=payload, headers=self.headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_get_blood_sugar_measurements_list(self) -> None:
        # 테스트 데이터 생성
        await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.FASTING,
            blood_glucose=95,
            has_exercised=False,
            has_medicated=False,
            measured_at=datetime.now(UTC),
        )
        await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.AFTER_BREAKFAST,
            blood_glucose=130,
            has_exercised=False,
            has_medicated=True,
            medicine_name="Insulin",
            measured_at=datetime.now(UTC),
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.get(self.api_path, headers=self.headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_get_blood_sugar_measurements_list_when_query_params_provided(self) -> None:
        now = datetime.now(UTC)
        # 테스트 데이터 생성
        await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.AFTER_BREAKFAST,
            blood_glucose=130,
            has_exercised=False,
            has_medicated=True,
            medicine_name="Insulin",
            minutes_since_medication=10,
            measured_at=now,
        )

        await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.BEFORE_LUNCH,
            blood_glucose=110,
            has_exercised=False,
            has_medicated=True,
            medicine_name="Insulin",
            minutes_since_medication=170,
            measured_at=now + timedelta(minutes=160),
        )

        # 필터 범위 밖 측정 기록 생성
        excluded_measurement = await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.BEFORE_LUNCH,
            blood_glucose=110,
            has_exercised=False,
            has_medicated=True,
            medicine_name="Insulin",
            minutes_since_medication=170,
            measured_at=now + timedelta(days=3),
        )

        query_params = {
            "start_date": str(now.date()),
            "end_date": str(now.date() + timedelta(days=1)),
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.get(self.api_path, headers=self.headers, params=query_params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert excluded_measurement not in data  # 필터링 되었는지 확인
        assert data[0]["measured_at"] < data[1]["measured_at"]  # measured_at 정렬 확인
        assert (
            data[0]["measure_type"] == BloodSugarMeasurementType.AFTER_BREAKFAST.label
        )  # 정렬된 순서에 따라 올바른값을 가지고 있는지 확인
        assert data[1]["measure_type"] == BloodSugarMeasurementType.BEFORE_LUNCH.label

    async def test_get_blood_sugar_measurement_by_id_success(self) -> None:
        measurement = await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.RANDOM,
            blood_glucose=110,
            has_exercised=False,
            has_medicated=False,
            measured_at=datetime.now(UTC),
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.get(f"{self.api_path}/{measurement.id}", headers=self.headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(measurement.id)
        assert data["blood_glucose"] == 110

    async def test_get_blood_sugar_measurement_not_found(self) -> None:
        random_uuid = uuid7()
        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.get(f"{self.api_path}/{random_uuid}", headers=self.headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Blood Sugar Measurement Not Found."

    async def test_get_blood_sugar_measurement_unauthorized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.get(self.api_path)  # 헤더 없음

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_blood_sugar_measurement_forbidden_other_user(self) -> None:
        # 다른 유저의 데이터 생성
        other_user = await User.create(
            email="other@example.com",
            hashed_password="password",
            nickname="다른사람",
            name="다른사람",
            phone_number="01011110000",
        )
        other_measurement = await BloodSugarMeasurement.create(
            user=other_user,
            measure_type=BloodSugarMeasurementType.FASTING,
            blood_glucose=100,
            has_exercised=False,
            has_medicated=False,
            measured_at=datetime.now(UTC),
        )

        # 현재 유저(self.user)로 다른 유저의 데이터를 조회 시도
        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.get(f"{self.api_path}/{other_measurement.id}", headers=self.headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_blood_sugar_measurement_success(self) -> None:
        measurement = await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.FASTING,
            blood_glucose=100,
            has_exercised=False,
            has_medicated=False,
            measured_at=datetime.now(UTC),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            response = await client.delete(f"{self.api_path}/{measurement.id}", headers=self.headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_blood_sugar_measurement_failed_when_already_deleted(self) -> None:
        measurement = await BloodSugarMeasurement.create(
            user=self.test_user,
            measure_type=BloodSugarMeasurementType.FASTING,
            blood_glucose=100,
            has_exercised=False,
            has_medicated=False,
            measured_at=datetime.now(UTC),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url=self.base_url) as client:
            # 여기서 1차 삭제
            await client.delete(f"{self.api_path}/{measurement.id}", headers=self.headers)
            # 2차 삭제요청
            response = await client.delete(f"{self.api_path}/{measurement.id}", headers=self.headers)

        # 이미 삭제된 측정 기록이므로 404 반환 여부 확인
        assert response.status_code == status.HTTP_404_NOT_FOUND
