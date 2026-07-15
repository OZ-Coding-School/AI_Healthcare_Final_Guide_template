from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers
from app.core.db.databases import close_tortoise, initialize_tortoise
from app.core.exceptions.exception_handler import initialize_exception_handlers
from app.core.utils.redis import close_redis_pool, initialize_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_exception_handlers(app)
    await initialize_tortoise()
    initialize_redis_pool()

    yield

    await close_tortoise()
    await close_redis_pool()


app = FastAPI(
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(v1_routers)
