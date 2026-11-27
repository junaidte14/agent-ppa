
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import api.main as app_module
import api.routes.chat as chat_api
from api.dependencies.chat import WEB_TOOL_POLICY


class FakeConversationService:
    """In-memory substitute for the PostgreSQL conversation service."""

    def __init__(self):
        self.conversations = {}

    def create_conversation(self, title="New conversation"):
        conversation_id = uuid4()

        self.conversations[conversation_id] = {
            "id": str(conversation_id),
            "messages": [],
        }

        return self.conversations[conversation_id]

    def get_conversation(self, conversation_id):
        conversation_id = UUID(str(conversation_id))
        return self.conversations.get(conversation_id)

    def append_messages(self, conversation_id, messages):
        conversation_id = UUID(str(conversation_id))

        conversation = self.conversations.get(conversation_id)

        if conversation is None:
            raise ValueError("Conversation not found.")

        for message in messages:
            conversation["messages"].append({
                "message_data": message.copy()
            })


@pytest.fixture
def fake_conversation_service(monkeypatch):
    service = FakeConversationService()

    monkeypatch.setattr(
        chat_api,
        "conversation_service",
        service,
    )

    return service


@pytest.fixture
def client(fake_conversation_service):
    app_module.app.dependency_overrides[
        chat_api.get_llm
    ] = lambda: object()

    with TestClient(app_module.app) as test_client:
        yield test_client

    app_module.app.dependency_overrides.clear()


def test_chat_returns_assistant_response(
    client,
    fake_conversation_service,
    monkeypatch,
):
    conversation = fake_conversation_service.create_conversation()
    conversation_id = UUID(conversation["id"])

    def fake_run_agent_turn(
        llm,
        messages,
        policy,
        approval_callback,
    ):
        assert approval_callback is None

        assert "message:send" not in policy.allowed_permissions
        assert "notes:delete" not in policy.allowed_permissions

        assert messages[-1] == {
            "role": "user",
            "content": "Hello, assistant!",
        }

        messages.append({
            "role": "assistant",
            "content": "Hello! How can I help?",
        })

        return "Hello! How can I help?"

    monkeypatch.setattr(
        chat_api,
        "run_agent_turn",
        fake_run_agent_turn,
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Hello, assistant!",
            "conversation_id": str(conversation_id),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["conversation_id"] == str(conversation_id)
    assert data["reply"] == "Hello! How can I help?"

    persisted_messages = fake_conversation_service.get_conversation(
        conversation_id
    )["messages"]

    assert [
        message["message_data"]["role"]
        for message in persisted_messages
    ] == ["user", "assistant"]


def test_chat_creates_new_conversation(
    client,
    fake_conversation_service,
    monkeypatch,
):
    def fake_run_agent_turn(
        llm,
        messages,
        policy,
        approval_callback,
    ):
        messages.append({
            "role": "assistant",
            "content": "New conversation started.",
        })

        return "New conversation started."

    monkeypatch.setattr(
        chat_api,
        "run_agent_turn",
        fake_run_agent_turn,
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Start a conversation.",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["reply"] == "New conversation started."
    assert data["conversation_id"]

    conversation = fake_conversation_service.get_conversation(
        data["conversation_id"]
    )

    assert conversation is not None

    assert [
        message["message_data"]["role"]
        for message in conversation["messages"]
    ] == ["user", "assistant"]


def test_chat_rejects_blank_message(client):

    response = client.post(
        "/api/chat",
        json={
            "message": "   ",
        },
    )

    assert response.status_code == 422


def test_chat_preserves_partial_history_on_agent_failure(
    client,
    fake_conversation_service,
    monkeypatch,
):
    conversation = fake_conversation_service.create_conversation()
    conversation_id = UUID(conversation["id"])

    def failing_agent(
        llm,
        messages,
        policy,
        approval_callback,
    ):
        messages.append({
            "role": "assistant",
            "content": "Incomplete response",
        })

        raise RuntimeError("Simulated agent failure")

    monkeypatch.setattr(
        chat_api,
        "run_agent_turn",
        failing_agent,
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Trigger an error.",
            "conversation_id": str(conversation_id),
        },
    )

    assert response.status_code == 502

    conversation = fake_conversation_service.get_conversation(
        conversation_id
    )

    persisted_messages = conversation["messages"]

    # The user message and partial assistant response are preserved.
    assert [
        message["message_data"]["role"]
        for message in persisted_messages
    ] == ["user", "assistant"]

    assert (
        persisted_messages[0]["message_data"]["content"]
        == "Trigger an error."
    )

    assert (
        persisted_messages[1]["message_data"]["content"]
        == "Incomplete response"
    )


def test_chat_rejects_nonexistent_conversation(client):

    response = client.post(
        "/api/chat",
        json={
            "message": "Hello",
            "conversation_id": str(uuid4()),
        },
    )

    assert response.status_code == 404


def test_web_policy_blocks_approval_required_tools():

    assert (
        "message:send"
        not in WEB_TOOL_POLICY.allowed_permissions
    )

    assert (
        "notes:delete"
        not in WEB_TOOL_POLICY.allowed_permissions
    )
