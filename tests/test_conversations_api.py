
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import api.main as app_module
import api.routes.conversations as conversations_api


CONVERSATION_ID = UUID("11111111-1111-1111-1111-111111111111")
MESSAGE_ID = UUID("22222222-2222-2222-2222-222222222222")

NOW = datetime(2026, 11, 28, 10, 0, tzinfo=timezone.utc)


def make_conversation(title="Test conversation"):
    return {
        "id": CONVERSATION_ID,
        "title": title,
        "created_at": NOW,
        "updated_at": NOW,
    }


def make_conversation_detail():
    conversation = make_conversation()

    return {
        **conversation,
        "messages": [
            {
                "id": MESSAGE_ID,
                "conversation_id": CONVERSATION_ID,
                "message_order": 1,
                "role": "user",
                "content": "Hello",
                "message_data": {
                    "role": "user",
                    "content": "Hello",
                },
                "created_at": NOW,
            }
        ],
    }


class FakeConversationService:

    def __init__(self):
        self.conversations = {
            str(CONVERSATION_ID): make_conversation_detail()
        }

        self.last_list_arguments = None
        self.last_rename_arguments = None

    def list_conversations(
        self,
        limit: int = 20,
        offset: int = 0,
    ):
        all_conversations = [
            {
                key: value
                for key, value in conversation.items()
                if key != "messages"
            }
            for conversation in self.conversations.values()
        ]

        items = all_conversations[offset:offset + limit]
        self.last_list_arguments = {
            "limit": limit,
            "offset": offset,
        }
        return {
            "items": items,
            "total": len(all_conversations),
            "limit": limit,
            "offset": offset,
        }

    def get_conversation(self, conversation_id):
        return self.conversations.get(str(conversation_id))

    def rename_conversation(self, conversation_id, title):
        self.last_rename_arguments = {
            "conversation_id": conversation_id,
            "title": title,
        }

        conversation = self.conversations.get(str(conversation_id))

        if conversation is None:
            return None

        conversation["title"] = title

        return {
            key: value
            for key, value in conversation.items()
            if key != "messages"
        }

    def delete_conversation(self, conversation_id):
        return self.conversations.pop(
            str(conversation_id),
            None,
        ) is not None


@pytest.fixture
def client(monkeypatch):
    fake_service = FakeConversationService()

    monkeypatch.setattr(
        conversations_api,
        "conversation_service",
        fake_service,
    )

    with TestClient(app_module.app) as test_client:
        yield test_client, fake_service


def test_list_conversations(client):
    test_client, _ = client

    response = test_client.get("/api/conversations")

    assert response.status_code == 200

    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(CONVERSATION_ID)
    assert data["items"][0]["title"] == "Test conversation"

    assert data["total"] == 1
    assert data["limit"] == 20
    assert data["offset"] == 0

def test_list_conversations_supports_pagination(client):
    test_client, fake_service = client

    response = test_client.get(
        "/api/conversations?limit=10&offset=20"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["limit"] == 10
    assert data["offset"] == 20
    assert data["total"] == 1
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0

    assert fake_service.last_list_arguments == {
        "limit": 10,
        "offset": 20,
    }

@pytest.mark.parametrize(
    "query",
    [
        "?limit=0",
        "?limit=101",
        "?offset=-1",
    ],
)
def test_list_conversations_rejects_invalid_pagination(
    client,
    query,
):
    test_client, _ = client

    response = test_client.get(
        f"/api/conversations{query}"
    )

    assert response.status_code == 422


def test_get_conversation(client):
    test_client, _ = client

    response = test_client.get(
        f"/api/conversations/{CONVERSATION_ID}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(CONVERSATION_ID)
    assert data["title"] == "Test conversation"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"
    assert data["messages"][0]["message_order"] == 1


def test_get_nonexistent_conversation_returns_404(client):
    test_client, _ = client

    response = test_client.get(
        "/api/conversations/33333333-3333-3333-3333-333333333333"
    )

    assert response.status_code == 404


def test_rename_conversation(client):
    test_client, fake_service = client

    response = test_client.patch(
        f"/api/conversations/{CONVERSATION_ID}",
        json={"title": "Updated title"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"

    assert fake_service.last_rename_arguments == {
        "conversation_id": CONVERSATION_ID,
        "title": "Updated title",
    }


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
    ],
)
def test_rename_conversation_rejects_invalid_title(
    client,
    title,
):
    test_client, _ = client

    response = test_client.patch(
        f"/api/conversations/{CONVERSATION_ID}",
        json={"title": title},
    )

    assert response.status_code == 422


def test_rename_nonexistent_conversation_returns_404(client):
    test_client, _ = client

    response = test_client.patch(
        "/api/conversations/33333333-3333-3333-3333-333333333333",
        json={"title": "Updated title"},
    )

    assert response.status_code == 404


def test_delete_conversation(client):
    test_client, _ = client

    response = test_client.delete(
        f"/api/conversations/{CONVERSATION_ID}"
    )

    assert response.status_code == 204

    # Verify the conversation is no longer available.
    get_response = test_client.get(
        f"/api/conversations/{CONVERSATION_ID}"
    )

    assert get_response.status_code == 404


def test_delete_nonexistent_conversation_returns_404(client):
    test_client, _ = client

    response = test_client.delete(
        "/api/conversations/33333333-3333-3333-3333-333333333333"
    )

    assert response.status_code == 404
