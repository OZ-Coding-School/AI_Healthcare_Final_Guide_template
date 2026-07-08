from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException

from app.core import logger, settings
from app.core.config import Env


async def http_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    http_exc = cast(HTTPException, exc)

    logger.warning(
        "[HTTPException] %s %s -> %s (%s)",
        request.method,
        request.url.path,
        http_exc.status_code,
        http_exc.detail,
    )

    return ORJSONResponse(
        status_code=http_exc.status_code,
        content={
            "message": http_exc.detail,
        },
    )


async def validation_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    validation_exc = cast(RequestValidationError, exc)
    if settings.ENV in [Env.LOCAL, Env.DEV]:
        logger.warning(
            "[ValidationError] %s %s\nrequest_body=%s\nerrors=%s",
            request.method,
            request.url.path,
            validation_exc.body,
            validation_exc.errors(),
        )
    else:
        logger.warning(
            "[ValidationError] %s %s\nerrors=%s",
            request.method,
            request.url.path,
            validation_exc.errors(),
        )

    return ORJSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "요청 데이터가 올바르지 않습니다.",
            "errors": validation_exc.errors(),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    logger.exception(
        "[Unhandled Exception] %s %s",
        request.method,
        request.url.path,
    )
    return ORJSONResponse(
        status_code=500,
        content={"code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."},
    )


def initialize_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
