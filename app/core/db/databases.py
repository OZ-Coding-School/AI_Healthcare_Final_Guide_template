from tortoise import Tortoise

from app.core import settings

TORTOISE_APP_MODELS = [
    "aerich.models",
    "app.models.user_models",
    "app.models.health_profiles",
    "app.models.disease_prediction_models",
    "app.models.challenge_models",
]

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": settings.DB_HOST,
                "port": settings.DB_PORT,
                "user": settings.DB_USER,
                "password": settings.DB_PASSWORD,
                "database": settings.DB_NAME,
                "command_timeout": settings.DB_CONNECT_TIMEOUT,
                "maxsize": settings.DB_CONNECTION_POOL_MAXSIZE,
            },
        },
    },
    "apps": {
        "models": {
            "models": TORTOISE_APP_MODELS,
        },
    },
    "timezone": "Asia/Seoul",
}


async def initialize_tortoise():
    await Tortoise.init(config=TORTOISE_ORM)


async def close_tortoise():
    await Tortoise.close_connections()
