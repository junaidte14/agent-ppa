from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database.models import Note

class NotesRepository:
    """
    PostgreSQL data-access layer for notes.

    The caller owns the SQLAlchemy session and transaction.
    This repository never commits, rolls back, or closes sessions.
    """

    @staticmethod
    def create(
        session: Session,
        title: str,
        content: str
    ) -> Note:
        note = Note(title=title, content=content)

        session.add(note)
        session.flush()
        session.refresh(note)

        return note

    @staticmethod
    def get_by_id(
        session: Session,
        note_id: UUID
    ) -> Note | None:
        statement = select(Note).where(
            Note.id == note_id
        )
        return session.scalar(statement=statement)

    @staticmethod
    def update(
        session: Session,
        note: Note,
        title: str | None = None,
        content: str | None = None
    ) -> Note:
        if title is not None:
            note.title = title

        if content is not None:
            note.content = content

        note.updated_at = func.now()

        session.flush()
        session.refresh(note)

        return note

    @staticmethod
    def delete(
        session: Session,
        note: Note
    ) -> None:
        session.delete(note)
        session.flush()