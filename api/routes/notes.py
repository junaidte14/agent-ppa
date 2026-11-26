
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas.notes import (
    CreateNoteRequest,
    DeleteNoteResponse,
    NoteListResponse,
    NoteResponse,
    NoteSearchResponse,
    UpdateNoteRequest,
)

from services.notes_service import NotesService, notes_service


router = APIRouter(
    prefix="/api/notes",
    tags=["Notes"],
)


# ---------------------------------------------------------
# Dependencies
# ---------------------------------------------------------

def get_notes_service() -> NotesService:
    return notes_service


# ---------------------------------------------------------
# Create note
# ---------------------------------------------------------

@router.post(
    "",
    response_model=NoteResponse,
    status_code=201,
)
def create_note(
    request: CreateNoteRequest,
    service: NotesService = Depends(get_notes_service),
):
    try:
        return service.create_note(
            title=request.title,
            content=request.content,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


# ---------------------------------------------------------
# List notes
# ---------------------------------------------------------

@router.get(
    "",
    response_model=NoteListResponse,
)
def list_notes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: NotesService = Depends(get_notes_service),
):
    return service.list_notes(
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------
# Search notes
# ---------------------------------------------------------

@router.get(
    "/search",
    response_model=NoteSearchResponse,
)
def search_notes(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: NotesService = Depends(get_notes_service),
):
    try:
        return service.search_notes(
            query=q,
            limit=limit,
            offset=offset,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


# ---------------------------------------------------------
# Get note
# ---------------------------------------------------------

@router.get(
    "/{note_id}",
    response_model=NoteResponse,
)
def get_note(
    note_id: UUID,
    service: NotesService = Depends(get_notes_service),
):
    note = service.get_note(note_id=note_id)

    if note is None:
        raise HTTPException(
            status_code=404,
            detail="Note not found.",
        )

    return note


# ---------------------------------------------------------
# Update note
# ---------------------------------------------------------

@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
)
def update_note(
    note_id: UUID,
    request: UpdateNoteRequest,
    service: NotesService = Depends(get_notes_service),
):
    try:
        note = service.update_note(
            note_id=note_id,
            title=request.title,
            content=request.content,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    if note is None:
        raise HTTPException(
            status_code=404,
            detail="Note not found.",
        )

    return note


# ---------------------------------------------------------
# Delete note
# ---------------------------------------------------------

@router.delete(
    "/{note_id}",
    response_model=DeleteNoteResponse,
)
def delete_note(
    note_id: UUID,
    service: NotesService = Depends(get_notes_service),
):
    deleted = service.delete_note(note_id=note_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Note not found.",
        )

    return DeleteNoteResponse(deleted=True)
