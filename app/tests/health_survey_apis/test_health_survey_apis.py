from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.enums import HabitStatus
from app.core.utils.jwt.provider import JWTProvider
from app.main import app
from app.models.health_profiles import MonthlyHealthSurvey
from app.models.user_models import User


class TestHealthSurveyAPI(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.jwt_provider = JWTProvider()

    async def _create_test_user(
        self, email: str = "survey_test@example.com", phone_number: str = "01099998888"
    ) -> User:
        return await User.create(
            email=email,
            hashed_password="hashed_password",
            nickname="테스터",
            name="테스터",
            phone_number=phone_number,
        )

    def _get_auth_header(self, user: User) -> dict[str, str]:
        token_pair = self.jwt_provider.issue_jwt_pair(user)
        return {"Authorization": f"Bearer {token_pair['access_token']}"}

    async def test_create_monthly_health_survey_success(self):
        user = await self._create_test_user()
        headers = self._get_auth_header(user)

        survey_data = {
            "smoking_status": HabitStatus.NEVER,
            "drinking_status": HabitStatus.NEVER,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "pulse": 70,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/health-survey/", json=survey_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED

        # DB 확인
        exists = await MonthlyHealthSurvey.filter(user=user).exists()
        assert exists is True

    async def test_create_monthly_health_survey_duplicate_fails(self):
        user = await self._create_test_user()
        headers = self._get_auth_header(user)

        survey_data = {
            "smoking_status": HabitStatus.NEVER,
            "drinking_status": HabitStatus.NEVER,
            "systolic_bp": 120,
            "diastolic_bp": 80,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 첫 번째 제출
            await client.post("/api/v1/health-survey/", json=survey_data, headers=headers)
            # 두 번째 제출 (같은 달)
            response = await client.post("/api/v1/health-survey/", json=survey_data, headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Monthly Health Survey already submitted this month."

    async def test_create_monthly_health_survey_validation_fails(self):
        user = await self._create_test_user()
        headers = self._get_auth_header(user)

        # 1. 흡연: CURRENT인데 빈도를 보내지 않은 경우
        survey_data_smoking = {
            "smoking_status": HabitStatus.CURRENT,
            "drinking_status": HabitStatus.NEVER,
            "systolic_bp": 120,
            "diastolic_bp": 80,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/health-survey/", json=survey_data_smoking, headers=headers)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
            assert "smoking_fr_per_day is required." in response.text

        # 2. 음주: CURRENT인데 빈도를 보내지 않은 경우
        survey_data_drinking = {
            "smoking_status": HabitStatus.NEVER,
            "drinking_status": HabitStatus.CURRENT,
            "systolic_bp": 120,
            "diastolic_bp": 80,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/health-survey/", json=survey_data_drinking, headers=headers)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
            assert "drinking_fr_per_week, drinking_amount_per_session are required." in response.text

    async def test_create_monthly_health_survey_normalization(self):
        user = await self._create_test_user("normalization@example.com", "01011110000")
        headers = self._get_auth_header(user)

        # 상태는 NEVER인데 빈도 데이터를 보낸 경우 -> None으로 정규화되어야 함
        survey_data = {
            "smoking_status": HabitStatus.NEVER,
            "smoking_fr_per_day": 10,
            "drinking_status": HabitStatus.NEVER,
            "drinking_fr_per_week": 3,
            "drinking_amount_per_session": 5,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "pulse": 70,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/health-survey/", json=survey_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED

        # DB에서 정규화 여부 확인
        survey = await MonthlyHealthSurvey.get(user=user)
        assert survey.smoking_fr_per_day is None
        assert survey.drinking_fr_per_week is None
        assert survey.drinking_amount_per_session is None

    async def test_create_monthly_health_survey_all_fields_success(self):
        user = await self._create_test_user("all_fields@example.com", "01022221111")
        headers = self._get_auth_header(user)

        survey_data = {
            "smoking_status": HabitStatus.CURRENT,
            "smoking_fr_per_day": 10,
            "drinking_status": HabitStatus.CURRENT,
            "drinking_fr_per_week": 2,
            "drinking_amount_per_session": 3,
            "systolic_bp": 130,
            "diastolic_bp": 85,
            "pulse": 75,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/health-survey/", json=survey_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED

        survey = await MonthlyHealthSurvey.get(user=user)
        assert survey.smoking_fr_per_day == 10
        assert survey.drinking_fr_per_week == 2
        assert survey.drinking_amount_per_session == 3

    async def test_get_monthly_health_survey_list(self):
        user = await self._create_test_user("filter_test@example.com", "01022223333")
        headers = self._get_auth_header(user)

        await MonthlyHealthSurvey.create(
            user=user,
            smoking_status=HabitStatus.NEVER,
            drinking_status=HabitStatus.NEVER,
            systolic_bp=120,
            diastolic_bp=80,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 올해 데이터 조회
            response = await client.get("/api/v1/health-survey/", headers=headers)
            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()) == 1

    async def test_get_monthly_health_survey_list_filter_success(self):
        user = await self._create_test_user("filter_test@example.com", "01022223333")
        headers = self._get_auth_header(user)

        from datetime import date
        # 작년 데이터 (수동으로 created_at 조절은 어려우므로, 로직상 어떻게 필터링하는지 확인 필요)
        # 서비스 코드: return await self.monthly_health_survey_repo.get_list(user_id, **filters.model_dump())
        # Repository 코드를 봐야 정확한 필터 동작을 알 수 있음.

        await MonthlyHealthSurvey.create(
            user=user,
            smoking_status=HabitStatus.NEVER,
            drinking_status=HabitStatus.NEVER,
            systolic_bp=120,
            diastolic_bp=80,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 올해 데이터 조회
            current_year = date.today().year
            response = await client.get(
                f"/api/v1/health-survey/?start_year={current_year}&end_year={current_year}", headers=headers
            )
            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()) == 1

            # 내년 데이터 조회 (없어야 함)
            response = await client.get(f"/api/v1/health-survey/?start_year={current_year + 1}", headers=headers)
            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()) == 0

    async def test_get_monthly_health_survey_list_invalid_filter_fails(self):
        user = await self._create_test_user("invalid_filter@example.com", "01033334444")
        headers = self._get_auth_header(user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # start_year > end_year
            response = await client.get("/api/v1/health-survey/?start_year=2024&end_year=2023", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "start_year must be less than or equal to end_year" in response.text

    async def test_get_monthly_health_survey_by_id_success(self):
        user = await self._create_test_user()
        headers = self._get_auth_header(user)

        survey = await MonthlyHealthSurvey.create(
            user=user,
            smoking_status=HabitStatus.NEVER,
            drinking_status=HabitStatus.NEVER,
            systolic_bp=120,
            diastolic_bp=80,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/health-survey/{survey.id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(survey.id)

    async def test_get_monthly_health_survey_by_id_not_found(self):
        user = await self._create_test_user()
        headers = self._get_auth_header(user)

        import uuid

        fake_id = uuid.uuid4()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/health-survey/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Monthly Health Survey Not Found."

    async def test_get_monthly_health_survey_by_id_forbidden(self):
        user1 = await self._create_test_user("user1@example.com", "01044445555")
        user2 = await self._create_test_user("user2@example.com", "01055556666")

        headers1 = self._get_auth_header(user1)

        # User 2의 데이터 생성
        survey_user2 = await MonthlyHealthSurvey.create(
            user=user2,
            smoking_status=HabitStatus.NEVER,
            drinking_status=HabitStatus.NEVER,
            systolic_bp=120,
            diastolic_bp=80,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # User 1이 User 2의 데이터를 조회 시도
            response = await client.get(f"/api/v1/health-survey/{survey_user2.id}", headers=headers1)

        # Repository.get_by_id 에서 user_id를 같이 필터링하므로 None이 반환되고,
        # Service에서 404를 발생시킴
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_unauthorized_access(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health-survey/")

        # 인증 헤더가 없으면 401
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
