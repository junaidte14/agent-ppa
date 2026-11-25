
import json
from typing import Any
from uuid import UUID

from tools.base import Tool
from tools.schemas import (
    CreateNoteInput,
    DeleteNoteInput,
    GetNoteInput,
    UpdateNoteInput,
    ListNotesInput,
    SearchNotesInput,
)
from services.notes_service import notes_service


def _json_result(data: dict[str, Any]) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
    )


def create_note(
    title: str,
    content: str,
) -> str:
    note = notes_service.create_note(
        title=title,
        content=content,
    )

    return _json_result({
        "status": "created",
        "note": note,
    })


def get_note(
    note_id: UUID,
) -> str:
    note = notes_service.get_note(
        note_id=note_id,
    )

    if note is None:
        return _json_result({
            "status": "not_found",
            "message": "The requested note does not exist.",
        })

    return _json_result({
        "status": "found",
        "note": note,
    })


def update_note(
    note_id: UUID,
    title: str | None = None,
    content: str | None = None,
) -> str:
    note = notes_service.update_note(
        note_id=note_id,
        title=title,
        content=content,
    )

    if note is None:
        return _json_result({
            "status": "not_found",
            "message": "The requested note does not exist.",
        })

    return _json_result({
        "status": "updated",
        "note": note,
    })


def delete_note(
    note_id: UUID,
) -> str:
    deleted = notes_service.delete_note(
        note_id=note_id,
    )

    if not deleted:
        return _json_result({
            "status": "not_found",
            "message": "The requested note does not exist.",
        })

    return _json_result({
        "status": "deleted",
        "note_id": str(note_id),
    })

def list_notes(
    limit: int = 20,
    offset: int = 0,
) -> str:
    result = notes_service.list_notes(
        limit=limit,
        offset=offset,
    )

    return _json_result({
        "status": "found",
        **result,
    })


def search_notes(
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> str:
    result = notes_service.search_notes(
        query=query,
        limit=limit,
        offset=offset,
    )

    return _json_result({
        "status": "found",
        **result,
    })

NOTE_TOOLS = [
    Tool(
        name="create_note",
        description=(
            "Create a personal note with a title and content. "
            "Use this when the user asks to save or remember "
            "information as a note."
        ),
        args_schema=CreateNoteInput,
        function=create_note,
        required_permission="notes:create",
    ),
    Tool(
        name="get_note",
        description=(
            "Retrieve a previously created note using its UUID."
        ),
        args_schema=GetNoteInput,
        function=get_note,
        required_permission="notes:read",
    ),
    Tool(
        name="update_note",
        description=(
            "Update the title or content of an existing note. "
            "The note UUID is required."
        ),
        args_schema=UpdateNoteInput,
        function=update_note,
        required_permission="notes:update",
    ),
    Tool(
        name="delete_note",
        description=(
            "Permanently delete an existing note. "
            "This action requires user approval."
        ),
        args_schema=DeleteNoteInput,
        function=delete_note,
        required_permission="notes:delete",
        requires_approval=True,
    ),
    Tool(
        name="list_notes",
        description=(
            "List saved notes, ordered by most recently updated. "
            "Supports pagination using limit and offset."
        ),
        args_schema=ListNotesInput,
        function=list_notes,
        required_permission="notes:read",
    ),
    Tool(
        name="search_notes",
        description=(
            "Search saved notes by matching text in their titles "
            "or content. Search is case-insensitive and supports "
            "pagination using limit and offset."
        ),
        args_schema=SearchNotesInput,
        function=search_notes,
        required_permission="notes:read",
    ),
]
