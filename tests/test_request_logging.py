import asyncio
import json
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.exception_handlers import app_exception_handler, unhandled_exception_handler
from app.core.exceptions import AppException, DeepSeekError
from app.main import app
from app.middleware.request_logging import request_logging_middleware


def _http_request(request_id: str | None = None) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/boom",
            "raw_path": b"/boom",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
            "scheme": "http",
            "root_path": "",
            "http_version": "1.1",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
        }
    )
    if request_id is not None:
        request.state.request_id = request_id
    return request


@pytest.fixture
def logging_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_logging_middleware)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/echo")
    async def echo(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    @app.get("/boom")
    async def boom() -> None:
        raise ValueError("boom")

    return app


@pytest.fixture
def logging_client(logging_app: FastAPI) -> TestClient:
    with TestClient(logging_app) as test_client:
        yield test_client


def test_middleware_sets_request_id_header(logging_client: TestClient) -> None:
    response = logging_client.get("/echo")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_middleware_exposes_request_id_via_request_state(logging_client: TestClient) -> None:
    response = logging_client.get("/echo")

    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_middleware_logs_request_started_and_finished(
    logging_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.middleware.request_logging"):
        response = logging_client.get("/echo")

    messages = [record.getMessage() for record in caplog.records]
    started = [message for message in messages if message.startswith("request_started")]
    finished = [message for message in messages if message.startswith("request_finished")]

    assert len(started) == 1
    assert len(finished) == 1
    assert f"request_id={response.headers['X-Request-ID']}" in started[0]
    assert "method=GET" in started[0]
    assert "path=/echo" in started[0]
    assert f"request_id={response.headers['X-Request-ID']}" in finished[0]
    assert f"status_code={response.status_code}" in finished[0]


def test_middleware_generates_unique_request_ids(logging_client: TestClient) -> None:
    first = logging_client.get("/echo")
    second = logging_client.get("/echo")

    assert first.headers["X-Request-ID"]
    assert second.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_middleware_logs_request_finished_on_unhandled_exception(
    logging_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        TestClient(logging_app, raise_server_exceptions=False) as test_client,
        caplog.at_level(logging.INFO, logger="app.middleware.request_logging"),
    ):
        response = test_client.get("/boom")

    assert response.status_code == 500
    assert response.headers["X-Request-ID"]

    finished = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("request_finished")
    ]
    assert len(finished) == 1
    assert f"request_id={response.headers['X-Request-ID']}" in finished[0]
    assert "status_code=500" in finished[0]


def test_unhandled_exception_handler_returns_json_500_with_request_id() -> None:
    response = asyncio.run(unhandled_exception_handler(_http_request("rid-1"), ValueError("boom")))

    assert response.status_code == 500
    assert json.loads(response.body) == {
        "error": "internal_error",
        "message": "Internal Server Error",
        "request_id": "rid-1",
    }


def test_unhandled_exception_handler_echoes_request_id_header() -> None:
    response = asyncio.run(unhandled_exception_handler(_http_request("rid-1"), ValueError("boom")))

    assert response.headers["X-Request-ID"] == "rid-1"


def test_unhandled_exception_handler_omits_header_without_request_id() -> None:
    response = asyncio.run(unhandled_exception_handler(_http_request(), ValueError("boom")))

    assert "X-Request-ID" not in response.headers
    assert "request_id" not in json.loads(response.body)


def test_unhandled_exception_handler_logs_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.core.exception_handlers"):
        asyncio.run(unhandled_exception_handler(_http_request("rid-9"), ValueError("boom")))

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.core.exception_handlers"
    ]
    assert len(messages) == 1
    assert "unhandled_exception" in messages[0]
    assert "request_id=rid-9" in messages[0]


def test_app_exception_handler_logs_server_error_with_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.core.exception_handlers"):
        asyncio.run(app_exception_handler(_http_request("rid-7"), DeepSeekError("upstream failure")))

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.core.exception_handlers"
    ]
    assert len(messages) == 1
    assert "app_exception" in messages[0]
    assert "request_id=rid-7" in messages[0]
    assert "error_code=deepseek_error" in messages[0]
    assert "status_code=502" in messages[0]


def test_app_exception_handler_does_not_log_client_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exc = AppException("bad request", status_code=400, error_code="bad_request")

    with caplog.at_level(logging.ERROR, logger="app.core.exception_handlers"):
        asyncio.run(app_exception_handler(_http_request(), exc))

    records = [
        record
        for record in caplog.records
        if record.name == "app.core.exception_handlers"
    ]
    assert records == []


def test_app_exception_handler_returns_json_with_request_id() -> None:
    response = asyncio.run(app_exception_handler(_http_request("rid-5"), DeepSeekError("boom")))

    assert response.status_code == 502
    assert response.headers["X-Request-ID"] == "rid-5"
    assert json.loads(response.body) == {
        "error": "deepseek_error",
        "message": "boom",
        "request_id": "rid-5",
    }


def test_app_exception_handler_omits_request_id_without_request_id() -> None:
    response = asyncio.run(
        app_exception_handler(_http_request(), AppException("bad request", status_code=400))
    )

    assert response.status_code == 400
    assert "X-Request-ID" not in response.headers
    assert json.loads(response.body) == {
        "error": "internal_error",
        "message": "bad request",
    }


def test_app_exception_handler_defaults_to_500() -> None:
    response = asyncio.run(app_exception_handler(_http_request("rid-3"), AppException("boom")))

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "rid-3"
    assert json.loads(response.body) == {
        "error": "internal_error",
        "message": "boom",
        "request_id": "rid-3",
    }


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (503, "api key missing"),
        (504, "upstream timeout"),
    ],
)
def test_deepseek_error_custom_status_codes(status_code: int, message: str) -> None:
    response = asyncio.run(
        app_exception_handler(
            _http_request("rid-4"),
            DeepSeekError(message, status_code=status_code),
        )
    )

    assert response.status_code == status_code
    assert response.headers["X-Request-ID"] == "rid-4"
    assert json.loads(response.body) == {
        "error": "deepseek_error",
        "message": message,
        "request_id": "rid-4",
    }


def test_real_app_health_response_has_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_real_app_validation_error_keeps_request_id_header(client: TestClient) -> None:
    response = client.post("/api/chat", json={})

    assert response.status_code == 422
    assert response.headers["X-Request-ID"]


def test_real_app_unhandled_exception_returns_json_500_with_request_id(
    override_chat_service, fake_chat_service
) -> None:
    fake_chat_service.error = ValueError("boom")
    override_chat_service(fake_chat_service)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post("/api/chat", json={"message": "你好"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"]
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["message"] == "Internal Server Error"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_real_app_handled_exception_returns_json_with_request_id(
    client: TestClient, override_chat_service, fake_chat_service
) -> None:
    fake_chat_service.error = DeepSeekError("upstream failure")
    override_chat_service(fake_chat_service)

    response = client.post("/api/chat", json={"message": "你好"})

    assert response.status_code == 502
    assert response.headers["X-Request-ID"]
    body = response.json()
    assert body["error"] == "deepseek_error"
    assert body["request_id"] == response.headers["X-Request-ID"]
