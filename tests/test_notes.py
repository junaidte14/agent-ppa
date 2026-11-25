
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from database.connection import SessionLocal
from database.models import Note
from repositories.notes_repository import NotesRepository
from services.notes_service import NotesService
from tools.notes import NOTE_TOOLS
from tools.policy import DEFAULT_TOOL_POLICY
from tools.registry import TOOL_REGISTRY, TOOL_DEFINITIONS
from tools.schemas import (
    CreateNoteInput,
    DeleteNoteInput,
    GetNoteInput,
    UpdateNoteInput,
)


# ---------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------

@pytest.fixture
def notes_service():
    """Use the configured PostgreSQL database."""
    return NotesService(session_factory=SessionLocal)


@pytest.fixture
def tracked_note_ids():
    """
    Track notes created by a test and remove them afterwards.

    This keeps the tests isolated without requiring a separate database.
    """
    note_ids = []

    yield note_ids

    if note_ids:
        with SessionLocal() as session:
            with session.begin():
                session.execute(
                    delete(Note).where(Note.id.in_(note_ids))
                )


def track_note(note_ids, note):
    """Add a note UUID to the test cleanup list."""
    note_ids.append(UUID(str(note["id"])) if isinstance(note, dict) else note.id)


def get_note_tools():
    return {tool.name: tool for tool in NOTE_TOOLS}


# ---------------------------------------------------------------------
# 1. Repository tests
# ---------------------------------------------------------------------

def test_repository_create_get_update_delete(tracked_note_ids):
    """Test the complete NotesRepository CRUD lifecycle."""

    with SessionLocal() as session:
        with session.begin():
            note = NotesRepository.create(
                session=session,
                title="Repository test",
                content="Initial note content",
            )
            note_id = note.id
            tracked_note_ids.append(note_id)

        with session.begin():
            retrieved = NotesRepository.get_by_id(
                session=session,
                note_id=note_id,
            )

            assert retrieved is not None
            assert retrieved.id == note_id
            assert retrieved.title == "Repository test"
            assert retrieved.content == "Initial note content"

        with session.begin():
            retrieved = NotesRepository.get_by_id(
                session=session,
                note_id=note_id,
            )

            updated = NotesRepository.update(
                session=session,
                note=retrieved,
                title="Updated repository test",
                content="Updated note content",
            )

            assert updated.title == "Updated repository test"
            assert updated.content == "Updated note content"

        with session.begin():
            retrieved = NotesRepository.get_by_id(
                session=session,
                note_id=note_id,
            )

            assert retrieved is not None

            NotesRepository.delete(
                session=session,
                note=retrieved,
            )

        with session.begin():
            deleted_note = NotesRepository.get_by_id(
                session=session,
                note_id=note_id,
            )

            assert deleted_note is None


def test_repository_get_nonexistent_note():
    with SessionLocal() as session:
        result = NotesRepository.get_by_id(
            session=session,
            note_id=uuid4(),
        )

        assert result is None


def test_repository_update_only_title(tracked_note_ids):
    with SessionLocal() as session:
        with session.begin():
            note = NotesRepository.create(
                session=session,
                title="Original title",
                content="Content must remain unchanged",
            )
            tracked_note_ids.append(note.id)

        with session.begin():
            note = NotesRepository.get_by_id(
                session=session,
                note_id=note.id,
            )

            updated = NotesRepository.update(
                session=session,
                note=note,
                title="New title",
            )

            assert updated.title == "New title"
            assert updated.content == "Content must remain unchanged"


def test_repository_update_only_content(tracked_note_ids):
    with SessionLocal() as session:
        with session.begin():
            note = NotesRepository.create(
                session=session,
                title="Title must remain unchanged",
                content="Original content",
            )
            tracked_note_ids.append(note.id)

        with session.begin():
            note = NotesRepository.get_by_id(
                session=session,
                note_id=note.id,
            )

            updated = NotesRepository.update(
                session=session,
                note=note,
                content="New content",
            )

            assert updated.title == "Title must remain unchanged"
            assert updated.content == "New content"


# ---------------------------------------------------------------------
# 2. Service tests
# ---------------------------------------------------------------------

def test_service_create_note(notes_service, tracked_note_ids):
    result = notes_service.create_note(
        title="Service test",
        content="Created through NotesService",
    )

    track_note(tracked_note_ids, result)

    assert result["title"] == "Service test"
    assert result["content"] == "Created through NotesService"
    assert isinstance(UUID(result["id"]), UUID)
    assert "created_at" in result
    assert "updated_at" in result


def test_service_strips_title(notes_service, tracked_note_ids):
    result = notes_service.create_note(
        title="  Trimmed title  ",
        content="Some content",
    )

    track_note(tracked_note_ids, result)

    assert result["title"] == "Trimmed title"


def test_service_get_note(notes_service, tracked_note_ids):
    created = notes_service.create_note(
        title="Get test",
        content="Find this note",
    )
    track_note(tracked_note_ids, created)

    result = notes_service.get_note(UUID(created["id"]))

    assert result is not None
    assert result["id"] == created["id"]
    assert result["title"] == "Get test"
    assert result["content"] == "Find this note"


def test_service_get_nonexistent_note(notes_service):
    result = notes_service.get_note(uuid4())

    assert result is None


def test_service_update_note(notes_service, tracked_note_ids):
    created = notes_service.create_note(
        title="Before update",
        content="Original content",
    )
    track_note(tracked_note_ids, created)

    result = notes_service.update_note(
        note_id=UUID(created["id"]),
        title="After update",
        content="Updated content",
    )

    assert result is not None
    assert result["id"] == created["id"]
    assert result["title"] == "After update"
    assert result["content"] == "Updated content"


def test_service_update_only_title(notes_service, tracked_note_ids):
    created = notes_service.create_note(
        title="Old title",
        content="Unchanged content",
    )
    track_note(tracked_note_ids, created)

    result = notes_service.update_note(
        note_id=UUID(created["id"]),
        title="New title",
    )

    assert result["title"] == "New title"
    assert result["content"] == "Unchanged content"


def test_service_update_only_content(notes_service, tracked_note_ids):
    created = notes_service.create_note(
        title="Unchanged title",
        content="Old content",
    )
    track_note(tracked_note_ids, created)

    result = notes_service.update_note(
        note_id=UUID(created["id"]),
        content="New content",
    )

    assert result["title"] == "Unchanged title"
    assert result["content"] == "New content"


def test_service_update_nonexistent_note(notes_service):
    result = notes_service.update_note(
        note_id=uuid4(),
        title="Does not exist",
    )

    assert result is None


def test_service_update_requires_at_least_one_field(
    notes_service,
):
    with pytest.raises(ValueError):
        notes_service.update_note(
            note_id=uuid4(),
        )


def test_service_delete_note(notes_service, tracked_note_ids):
    created = notes_service.create_note(
        title="Delete test",
        content="This note will be deleted",
    )
    tracked_note_ids.append(created["id"])

    result = notes_service.delete_note(
        UUID(created["id"])
    )

    assert result is True

    retrieved = notes_service.get_note(
        UUID(created["id"])
    )

    assert retrieved is None


def test_service_delete_nonexistent_note(notes_service):
    result = notes_service.delete_note(uuid4())

    assert result is False


@pytest.mark.parametrize(
    "title",
    [
        "",
        " ",
        "   ",
    ],
)
def test_service_rejects_empty_title(notes_service, title):
    with pytest.raises(ValueError):
        notes_service.create_note(
            title=title,
            content="Valid content",
        )


def test_service_rejects_title_longer_than_255_characters(
    notes_service,
):
    with pytest.raises(ValueError):
        notes_service.create_note(
            title="a" * 256,
            content="Valid content",
        )


@pytest.mark.parametrize(
    "content",
    [
        "",
        " ",
        "   ",
    ],
)
def test_service_rejects_empty_content(notes_service, content):
    with pytest.raises(ValueError):
        notes_service.create_note(
            title="Valid title",
            content=content,
        )


def test_service_rejects_non_string_title(notes_service):
    with pytest.raises(ValueError):
        notes_service.create_note(
            title=123,
            content="Valid content",
        )


def test_service_rejects_non_string_content(notes_service):
    with pytest.raises(ValueError):
        notes_service.create_note(
            title="Valid title",
            content=123,
        )


def test_service_serializes_timezone_aware_timestamps(
    notes_service,
    tracked_note_ids,
):
    result = notes_service.create_note(
        title="Timestamp test",
        content="Check timestamps",
    )
    track_note(tracked_note_ids, result)

    from datetime import datetime

    created_at = datetime.fromisoformat(result["created_at"])
    updated_at = datetime.fromisoformat(result["updated_at"])

    assert created_at.tzinfo is not None
    assert updated_at.tzinfo is not None


# ---------------------------------------------------------------------
# 3. PostgreSQL database constraint tests
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    ("title", "content"),
    [
        ("   ", "Valid content"),
        ("Valid title", "   "),
    ],
)
def test_postgresql_rejects_empty_note_fields(title, content):
    """
    Verify that PostgreSQL constraints protect the data even
    when the application service is bypassed.
    """

    with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(
                    Note(
                        title=title,
                        content=content,
                    )
                )
                session.flush()


# ---------------------------------------------------------------------
# 4. Pydantic schema tests
# ---------------------------------------------------------------------

def test_create_note_schema_accepts_valid_input():
    data = CreateNoteInput.model_validate(
        {
            "title": "Schema test",
            "content": "Valid content",
        }
    )

    assert data.title == "Schema test"
    assert data.content == "Valid content"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content": "Valid content"},
        {"title": "Valid title", "content": ""},
        {
            "title": "a" * 256,
            "content": "Valid content",
        },
    ],
)
def test_create_note_schema_rejects_invalid_input(payload):
    with pytest.raises(ValueError):
        CreateNoteInput.model_validate(payload)


def test_create_note_schema_rejects_extra_fields():
    with pytest.raises(ValueError):
        CreateNoteInput.model_validate(
            {
                "title": "Valid title",
                "content": "Valid content",
                "unexpected": "not allowed",
            }
        )

def test_get_note_schema_rejects_invalid_uuid():
    with pytest.raises(ValueError):
        GetNoteInput.model_validate(
            {"note_id": "not-a-uuid"}
        )


def test_get_note_schema_accepts_uuid():
    note_id = uuid4()

    data = GetNoteInput.model_validate_json(
        json.dumps({"note_id": str(note_id)})
    )

    assert data.note_id == note_id


def test_update_note_schema_accepts_title_only():
    note_id = uuid4()

    data = UpdateNoteInput.model_validate_json(
        json.dumps({
            "note_id": str(note_id),
            "title": "New title",
        })
    )

    assert data.note_id == note_id
    assert data.title == "New title"


def test_update_note_schema_accepts_content_only():
    note_id = uuid4()

    data = UpdateNoteInput.model_validate_json(
        json.dumps({
            "note_id": str(note_id),
            "content": "New content",
        })
    )

    assert data.note_id == note_id
    assert data.content == "New content"


def test_delete_note_schema_accepts_uuid():
    note_id = uuid4()

    data = DeleteNoteInput.model_validate_json(
        json.dumps({"note_id": str(note_id)})
    )

    assert data.note_id == note_id


def test_update_note_schema_rejects_no_update_fields():
    with pytest.raises(ValueError):
        UpdateNoteInput.model_validate(
            {"note_id": str(uuid4())}
        )


# ---------------------------------------------------------------------
# 5. Tool registration and permission tests
# ---------------------------------------------------------------------

def test_all_note_tools_are_registered():
    expected_tools = {
        "create_note",
        "get_note",
        "update_note",
        "delete_note",
    }

    assert expected_tools.issubset(TOOL_REGISTRY.keys())



def test_note_tools_are_in_llm_definitions():
    tool_names = {
        definition["function"]["name"]
        for definition in TOOL_DEFINITIONS
    }

    assert {
        "create_note",
        "get_note",
        "update_note",
        "delete_note",
    }.issubset(tool_names)


@pytest.mark.parametrize(
    ("tool_name", "permission"),
    [
        ("create_note", "notes:create"),
        ("get_note", "notes:read"),
        ("update_note", "notes:update"),
        ("delete_note", "notes:delete"),
    ],
)
def test_note_tool_permissions(tool_name, permission):
    tool = TOOL_REGISTRY[tool_name]

    assert tool.required_permission == permission
    assert DEFAULT_TOOL_POLICY.is_allowed(permission)


def test_delete_note_requires_approval():
    tool = TOOL_REGISTRY["delete_note"]

    assert tool.requires_approval is True


@pytest.mark.parametrize(
    "tool_name",
    [
        "create_note",
        "get_note",
        "update_note",
    ],
)
def test_other_note_tools_do_not_require_approval(tool_name):
    tool = TOOL_REGISTRY[tool_name]

    assert tool.requires_approval is False


# ---------------------------------------------------------------------
# 6. Note tool execution tests
# ---------------------------------------------------------------------

def test_create_note_tool_returns_json(tracked_note_ids):
    tool = get_note_tools()["create_note"]

    result = json.loads(
        tool.function(
            title="Tool creation test",
            content="Created through the note tool",
        )
    )

    assert result["status"] == "created"
    assert result["note"]["title"] == "Tool creation test"
    assert result["note"]["content"] == (
        "Created through the note tool"
    )

    track_note(tracked_note_ids, result["note"])


def test_get_note_tool_returns_existing_note(tracked_note_ids):
    create_tool = get_note_tools()["create_note"]
    get_tool = get_note_tools()["get_note"]

    created = json.loads(
        create_tool.function(
            title="Tool retrieval test",
            content="Retrieve this note",
        )
    )

    track_note(tracked_note_ids, created["note"])

    result = json.loads(
        get_tool.function(
            note_id=UUID(created["note"]["id"])
        )
    )

    assert result["status"] == "found"
    assert result["note"]["id"] == created["note"]["id"]
    assert result["note"]["title"] == "Tool retrieval test"


def test_get_note_tool_returns_not_found_for_missing_note():
    tool = get_note_tools()["get_note"]

    result = json.loads(
        tool.function(note_id=uuid4())
    )

    assert result["status"] == "not_found"


def test_update_note_tool_returns_updated_note(
    tracked_note_ids,
):
    tools = get_note_tools()

    created = json.loads(
        tools["create_note"].function(
            title="Before tool update",
            content="Original content",
        )
    )

    track_note(tracked_note_ids, created["note"])

    result = json.loads(
        tools["update_note"].function(
            note_id=UUID(created["note"]["id"]),
            title="After tool update",
            content="Updated content",
        )
    )

    assert result["status"] == "updated"
    assert result["note"]["title"] == "After tool update"
    assert result["note"]["content"] == "Updated content"


def test_update_note_tool_returns_not_found():
    tool = get_note_tools()["update_note"]

    result = json.loads(
        tool.function(
            note_id=uuid4(),
            title="Updated title",
        )
    )

    assert result["status"] == "not_found"


def test_delete_note_tool_deletes_existing_note(
    tracked_note_ids,
):
    tools = get_note_tools()

    created = json.loads(
        tools["create_note"].function(
            title="Tool deletion test",
            content="This note should be deleted",
        )
    )

    note_id = UUID(created["note"]["id"])
    tracked_note_ids.append(note_id)

    result = json.loads(
        tools["delete_note"].function(
            note_id=note_id,
        )
    )

    assert result["status"] == "deleted"
    assert result["note_id"] == str(note_id)

    retrieved = NotesService().get_note(note_id)

    assert retrieved is None


def test_delete_note_tool_returns_not_found():
    tool = get_note_tools()["delete_note"]

    result = json.loads(
        tool.function(note_id=uuid4())
    )

    assert result["status"] == "not_found"
