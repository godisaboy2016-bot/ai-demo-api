import logging
import sys
import time
import uuid

from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


async def request_logging_middleware(request: Request, call_next) -> Response:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()

    logger.info(
        "request_started request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    response = None
    try:
        response = await call_next(request)
    finally:
        duration_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        if response is None:
            logger.error(
                "request_finished request_id=%s status_code=500 duration_ms=%s",
                request_id,
                duration_ms,
                exc_info=sys.exc_info(),
            )
        else:
            response.headers["X-Request-ID"] = request_id

            logger.info(
                "request_finished request_id=%s status_code=%s duration_ms=%s",
                request_id,
                response.status_code,
                duration_ms,
            )

    return response
