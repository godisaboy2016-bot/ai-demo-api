import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.models.chat_message import ChatMessage


def _register(
    auth_client: TestClient, email: str, password: str = "password123"
) -> dict:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def _login(
    auth_client: TestClient, email: str, password: str = "password123"
) -> dict[str, str]:
    response = auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_messages(
    factory,
    user_id: UUID,
    *,
    count: int = 5,
    conversation_id: UUID | None = None,
) -> list[dict]:
    """Insert messages with strictly increasing created_at, oldest first."""

    base = datetime.now(UTC)

    async def _insert() -> list[dict]:
        async with factory() as session:
            messages = [
                ChatMessage(
                    user_id=user_id,
                    conversation_id=(
                        conversation_id if conversation_id is not None else uuid4()
                    ),
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"message-{i}",
                    model="deepseek-chat" if i % 2 else None,
                    created_at=base + timedelta(seconds=i),
                )
                for i in range(count)
            ]
            session.add_all(messages)
            await session.commit()
            return [
                {
                    "id": m.id,
                    "conversation_id": m.conversation_id,
                    "role": m.role,
                    "content": m.content,
                    "model": m.model,
                    "created_at": m.created_at,
                }
                for m in messages
            ]

    return asyncio.run(_insert())


def test_history_requires_auth(auth_client: TestClient) -> None:
    response = auth_client.get("/api/chat/history")

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_history_empty_returns_200(auth_client: TestClient, db_session_override) -> None:
    _register(auth_client, "empty@example.com")
    headers = _login(auth_client, "empty@example.com")

    response = auth_client.get("/api/chat/history", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_history_returns_own_messages_newest_first(
    auth_client: TestClient, db_session_override
) -> None:
    user = _register(auth_client, "alice@example.com")
    _seed_messages(db_session_override, UUID(user["id"]), count=5)
    headers = _login(auth_client, "alice@example.com")

    response = auth_client.get("/api/chat/history", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert [m["content"] for m in data["items"]] == [
        f"message-{i}" for i in range(4, -1, -1)
    ]
    assert data["next_cursor"] is None
    assert data["items"][0]["role"] == "user"
    assert data["items"][0]["model"] is None
    assert data["items"][1]["role"] == "assistant"
    assert data["items"][1]["model"] == "deepseek-chat"


def test_history_hides_other_users_messages(
    auth_client: TestClient, db_session_override
) -> None:
    alice = _register(auth_client, "alice@example.com")
    bob = _register(auth_client, "bob@example.com")
    _seed_messages(db_session_override, UUID(alice["id"]), count=3)
    _seed_messages(db_session_override, UUID(bob["id"]), count=2)
    headers = _login(auth_client, "alice@example.com")

    response = auth_client.get("/api/chat/history", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert {m["content"] for m in data["items"]} == {
        "message-0",
        "message-1",
        "message-2",
    }


def test_history_limit_applies(auth_client: TestClient, db_session_override) -> None:
    user = _register(auth_client, "alice@example.com")
    _seed_messages(db_session_override, UUID(user["id"]), count=5)
    headers = _login(auth_client, "alice@example.com")

    response = auth_client.get("/api/chat/history?limit=2", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert [m["content"] for m in data["items"]] == ["message-4", "message-3"]
    assert data["next_cursor"] is not None


def test_history_default_limit_is_20(
    auth_client: TestClient, db_session_override
) -> None:
    user = _register(auth_client, "alice@example.com")
    _seed_messages(db_session_override, UUID(user["id"]), count=25)
    headers = _login(auth_client, "alice@example.com")

    response = auth_client.get("/api/chat/history", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 20
    assert data["next_cursor"] is not None


def test_history_limit_bounds_rejected(
    auth_client: TestClient, db_session_override
) -> None:
    _register(auth_client, "alice@example.com")
    headers = _login(auth_client, "alice@example.com")

    for limit in (0, 101):
        response = auth_client.get(
            f"/api/chat/history?limit={limit}",
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["error"] == "validation_error"


def test_history_cursor_pagination(
    auth_client: TestClient, db_session_override
) -> None:
    user = _register(auth_client, "alice@example.com")
    _seed_messages(db_session_override, UUID(user["id"]), count=5)
    headers = _login(auth_client, "alice@example.com")

    page1 = auth_client.get(
        "/api/chat/history?limit=2",
        headers=headers,
    ).json()
    page2 = auth_client.get(
        f"/api/chat/history?limit=2&cursor={page1['next_cursor']}",
        headers=headers,
    ).json()
    page3 = auth_client.get(
        f"/api/chat/history?limit=2&cursor={page2['next_cursor']}",
        headers=headers,
    ).json()

    assert [m["content"] for m in page1["items"]] == ["message-4", "message-3"]
    assert page1["next_cursor"] is not None
    assert [m["content"] for m in page2["items"]] == ["message-2", "message-1"]
    assert page2["next_cursor"] is not None
    assert [m["content"] for m in page3["items"]] == ["message-0"]
    assert page3["next_cursor"] is None

    page_ids = [m["id"] for m in page1["items"] + page2["items"] + page3["items"]]
    assert len(page_ids) == 5
    assert len(set(page_ids)) == 5


def test_history_filters_by_conversation(
    auth_client: TestClient, db_session_override
) -> None:
    user = _register(auth_client, "alice@example.com")
    conv_a = uuid4()
    conv_b = uuid4()
    _seed_messages(
        db_session_override,
        UUID(user["id"]),
        count=2,
        conversation_id=conv_a,
    )
    _seed_messages(
        db_session_override,
        UUID(user["id"]),
        count=2,
        conversation_id=conv_b,
    )
    headers = _login(auth_client, "alice@example.com")

    response = auth_client.get(
        f"/api/chat/history?conversation_id={conv_a}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert all(m["conversation_id"] == str(conv_a) for m in data["items"])


def test_history_invalid_cursor_returns_422(
    auth_client: TestClient, db_session_override
) -> None:
    user = _register(auth_client, "alice@example.com")
    _seed_messages(db_session_override, UUID(user["id"]), count=1)
    headers = _login(auth_client, "alice@example.com")

    response = auth_client.get(
        "/api/chat/history?cursor=not-a-cursor",
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
