from fastapi import APIRouter

from app.apis.v1.annual_health_screening_apis import annual_health_screening_router
from app.apis.v1.auth_routers import auth_router
from app.apis.v1.blood_sugar_measurement_routers import blood_sugar_measurement_router
from app.apis.v1.health_profile_routers import health_profile_router
from app.apis.v1.health_survey_routers import health_survey_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(health_profile_router)
v1_routers.include_router(health_survey_router)
v1_routers.include_router(blood_sugar_measurement_router)
v1_routers.include_router(annual_health_screening_router)
