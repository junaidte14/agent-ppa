
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from database.connection import SessionLocal
from database.models import ConversationMessage
from services.conversation_service import ConversationService


@pytest.fixture
def conversation_service():
    return ConversationService(session_factory=SessionLocal)


@pytest.fixture
def tracked_conversation_ids(conversation_service):
    conversation_ids = []

    yield conversation_ids

    for conversation_id in conversation_ids:
        conversation_service.delete_conversation(
            UUID(conversation_id)
        )


def create_tracked_conversation(
    conversation_service,
    tracked_conversation_ids,
    title="Test conversation",
):
    conversation = conversation_service.create_conversation(title)

    tracked_conversation_ids.append(conversation["id"])

    return conversation


def test_create_and_get_conversation(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
        "Persistence test",
    )

    assert created["title"] == "Persistence test"
    assert created["id"]
    assert created["created_at"]
    assert created["updated_at"]

    retrieved = conversation_service.get_conversation(
        UUID(created["id"])
    )

    assert retrieved is not None
    assert retrieved["id"] == created["id"]
    assert retrieved["title"] == "Persistence test"
    assert retrieved["messages"] == []


def test_list_conversations(
    conversation_service,
    tracked_conversation_ids,
):
    first = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
        "First test conversation",
    )

    second = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
        "Second test conversation",
    )

    conversations = conversation_service.list_conversations(
        limit=100,
        offset=0,
    )

    conversation_ids = {
        conversation["id"] for conversation in conversations
    }

    assert first["id"] in conversation_ids
    assert second["id"] in conversation_ids


def test_rename_conversation(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
    )

    renamed = conversation_service.rename_conversation(
        UUID(created["id"]),
        "Updated conversation title",
    )

    assert renamed is not None
    assert renamed["title"] == "Updated conversation title"


def test_delete_conversation(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
    )

    conversation_id = UUID(created["id"])

    deleted = conversation_service.delete_conversation(
        conversation_id
    )

    assert deleted is True

    retrieved = conversation_service.get_conversation(
        conversation_id
    )

    assert retrieved is None

    # Avoid attempting to delete the same conversation during cleanup.
    tracked_conversation_ids.remove(created["id"])


def test_append_and_retrieve_messages(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
    )

    messages = [
        {
            "role": "user",
            "content": "Calculate 125 * 8",
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "calculate",
                        "arguments": '{"expression":"125 * 8"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": "1000",
        },
        {
            "role": "assistant",
            "content": "125 multiplied by 8 is 1000.",
        },
    ]

    saved = conversation_service.append_messages(
        UUID(created["id"]),
        messages,
    )

    assert len(saved) == 4

    retrieved = conversation_service.get_conversation(
        UUID(created["id"])
    )

    assert retrieved is not None
    assert len(retrieved["messages"]) == 4

    stored_messages = retrieved["messages"]

    assert [message["role"] for message in stored_messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]

    assert stored_messages[0]["content"] == "Calculate 125 * 8"

    # Verify that the complete tool-call structure survives JSONB storage.
    assert stored_messages[1]["message_data"]["tool_calls"] == (
        messages[1]["tool_calls"]
    )

    assert stored_messages[2]["message_data"]["tool_call_id"] == "call_123"

    # Verify database-generated ordering values.
    order_values = [
        message["message_order"] for message in stored_messages
    ]

    assert order_values == sorted(order_values)
    assert len(set(order_values)) == len(order_values)


def test_message_order_is_preserved_across_multiple_appends(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
    )

    conversation_id = UUID(created["id"])

    conversation_service.append_messages(
        conversation_id,
        [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
        ],
    )

    conversation_service.append_messages(
        conversation_id,
        [
            {"role": "user", "content": "Second message"},
            {"role": "assistant", "content": "Second response"},
        ],
    )

    retrieved = conversation_service.get_conversation(
        conversation_id
    )

    assert retrieved is not None

    stored_messages = retrieved["messages"]

    assert [
        message["content"] for message in stored_messages
    ] == [
        "First message",
        "First response",
        "Second message",
        "Second response",
    ]


def test_delete_conversation_cascades_to_messages(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
    )

    conversation_id = UUID(created["id"])

    conversation_service.append_messages(
        conversation_id,
        [
            {"role": "user", "content": "Message to delete"},
            {"role": "assistant", "content": "Response to delete"},
        ],
    )

    conversation_service.delete_conversation(conversation_id)
    tracked_conversation_ids.remove(created["id"])

    with SessionLocal() as session:
        remaining_messages = session.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id
            )
        )

    assert remaining_messages == 0


def test_create_conversation_rejects_invalid_titles(
    conversation_service,
):
    with pytest.raises(ValueError):
        conversation_service.create_conversation("   ")

    with pytest.raises(ValueError):
        conversation_service.create_conversation("x" * 256)


def test_append_messages_rejects_invalid_input(
    conversation_service,
    tracked_conversation_ids,
):
    created = create_tracked_conversation(
        conversation_service,
        tracked_conversation_ids,
    )

    conversation_id = UUID(created["id"])

    with pytest.raises(ValueError):
        conversation_service.append_messages(
            conversation_id,
            [],
        )

    with pytest.raises(ValueError):
        conversation_service.append_messages(
            conversation_id,
            [{"content": "Missing role"}],
        )

    with pytest.raises(ValueError):
        conversation_service.append_messages(
            conversation_id,
            [{"role": "user", "content": 123}],
        )

    with pytest.raises(ValueError):
        conversation_service.append_messages(
            conversation_id,
            [{"role": "user", "content": object()}],
        )


def test_append_messages_rejects_nonexistent_conversation(
    conversation_service,
):
    with pytest.raises(LookupError, match="Conversation not found"):
        conversation_service.append_messages(
            uuid4(),
            [{"role": "user", "content": "Hello"}],
        )


def test_rename_nonexistent_conversation_returns_none(
    conversation_service,
):
    result = conversation_service.rename_conversation(
        uuid4(),
        "New title",
    )

    assert result is None


def test_delete_nonexistent_conversation_returns_false(
    conversation_service,
):
    result = conversation_service.delete_conversation(uuid4())

    assert result is False


def test_list_conversations_validates_pagination(
    conversation_service,
):
    with pytest.raises(ValueError):
        conversation_service.list_conversations(limit=0)

    with pytest.raises(ValueError):
        conversation_service.list_conversations(limit=101)

    with pytest.raises(ValueError):
        conversation_service.list_conversations(offset=-1)
