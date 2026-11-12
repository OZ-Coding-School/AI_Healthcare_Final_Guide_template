from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException

from app.core import logger


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
    # Pydantic 오류에는 거부된 실제 입력값(input/context)이 포함될 수 있으므로
    # 로그와 응답에는 필드 위치와 일반 오류 설명만 남깁니다.
    safe_errors = [
        {key: error[key] for key in ("loc", "msg", "type") if key in error}
        for error in validation_exc.errors()
    ]
    logger.warning(
        "[ValidationError] %s %s\nerrors=%s",
        request.method,
        request.url.path,
        safe_errors,
    )

    return ORJSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "요청 데이터가 올바르지 않습니다.",
            "errors": safe_errors,
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
