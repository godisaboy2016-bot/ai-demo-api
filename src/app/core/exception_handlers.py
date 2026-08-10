import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    """
    Handle known application exceptions.
    """

    request_id = getattr(request.state, "request_id", None)

    if exc.status_code >= 500:
        logger.error(
            "app_exception request_id=%s error_code=%s status_code=%s message=%s",
            request_id,
            exc.error_code,
            exc.status_code,
            exc.message,
            exc_info=exc,
        )

    content = {
        "error": exc.error_code,
        "message": exc.message,
    }
    if request_id:
        content["request_id"] = request_id

    response = JSONResponse(
        status_code=exc.status_code,
        content=content,
    )
    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle request validation errors with the unified 422 contract.
    """

    request_id = getattr(request.state, "request_id", None)

    content = {
        "error": "validation_error",
        "message": "Invalid request",
    }
    if request_id:
        content["request_id"] = request_id

    response = JSONResponse(
        status_code=422,
        content=content,
    )
    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle unhandled exceptions: log the traceback and return a JSON 500.
    """

    request_id = getattr(request.state, "request_id", None)

    logger.exception("unhandled_exception request_id=%s", request_id)

    content = {
        "error": "internal_error",
        "message": "Internal Server Error",
    }
    if request_id:
        content["request_id"] = request_id

    response = JSONResponse(
        status_code=500,
        content=content,
    )
    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response
