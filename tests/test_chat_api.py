from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import api.main as chat_api


@pytest.fixture
def client():

    chat_api.app.dependency_overrides[
        chat_api.get_llm
    ] = lambda: object()

    with TestClient(chat_api.app) as test_client:
        yield test_client

    chat_api.app.dependency_overrides.clear()


def test_chat_returns_assistant_response(
    client,
    monkeypatch
):

    conversation_id = uuid4()

    def fake_run_agent_turn(
        llm,
        messages,
        policy,
        approval_callback
    ):

        assert approval_callback is None

        assert (
            "message:send"
            not in policy.allowed_permissions
        )

        assert (
            "notes:delete"
            not in policy.allowed_permissions
        )

        assert messages[-1] == {
            "role": "user",
            "content": "Hello, assistant!"
        }

        messages.append({
            "role": "assistant",
            "content": "Hello! How can I help?"
        })

        return "Hello! How can I help?"

    monkeypatch.setattr(
        chat_api,
        "run_agent_turn",
        fake_run_agent_turn
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Hello, assistant!",
            "conversation_id": str(conversation_id)
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["conversation_id"] == str(
        conversation_id
    )

    assert data["reply"] == (
        "Hello! How can I help?"
    )


def test_chat_creates_new_conversation(
    client,
    monkeypatch
):

    def fake_run_agent_turn(
        llm,
        messages,
        policy,
        approval_callback
    ):

        messages.append({
            "role": "assistant",
            "content": "New conversation started."
        })

        return "New conversation started."

    monkeypatch.setattr(
        chat_api,
        "run_agent_turn",
        fake_run_agent_turn
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Start a conversation."
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["reply"] == (
        "New conversation started."
    )

    assert data["conversation_id"]


def test_chat_rejects_blank_message(client):

    response = client.post(
        "/api/chat",
        json={
            "message": "   "
        }
    )

    assert response.status_code == 422


def test_chat_rolls_back_history_on_agent_failure(
    client,
    monkeypatch
):

    conversation_id = uuid4()

    def failing_agent(
        llm,
        messages,
        policy,
        approval_callback
    ):

        messages.append({
            "role": "assistant",
            "content": "Incomplete response"
        })

        raise RuntimeError("Simulated agent failure")

    monkeypatch.setattr(
        chat_api,
        "run_agent_turn",
        failing_agent
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Trigger an error.",
            "conversation_id": str(conversation_id)
        }
    )

    assert response.status_code == 502

    conversation = (
        chat_api.conversation_store.get_or_create(
            conversation_id
        )
    )

    # The failed user turn and incomplete assistant
    # response must not remain in conversation history.
    assert len(conversation.messages) == 1

    assert conversation.messages[0]["role"] == "system"


def test_web_policy_blocks_approval_required_tools():

    assert (
        "message:send"
        not in chat_api.WEB_TOOL_POLICY.allowed_permissions
    )

    assert (
        "notes:delete"
        not in chat_api.WEB_TOOL_POLICY.allowed_permissions
    )