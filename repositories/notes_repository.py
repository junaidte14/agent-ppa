from uuid import UUID
from sqlalchemy import func, select, or_
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

    @staticmethod
    def list_notes(
        session: Session,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Note], int]:
        """
        Return a page of notes and the total number of notes.

        Ordering is deterministic:
        newest updated first, UUID ascending as tie-breaker.
        """

        count_statement = (
            select(func.count())
            .select_from(Note)
        )

        total = session.scalar(count_statement) or 0

        statement = (
            select(Note)
            .order_by(
                Note.updated_at.desc(),
                Note.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        notes = list(session.scalars(statement).all())

        return notes, total

    @staticmethod
    def search_notes(
        session: Session,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Note], int]:
        """
        Search note titles and content.

        Percent, underscore, and backslash in the search
        query are escaped so they are treated literally
        rather than as SQL LIKE wildcards.
        """

        escaped_query = (
            query
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        pattern = f"%{escaped_query}%"

        search_filter = or_(
            Note.title.ilike(pattern, escape="\\"),
            Note.content.ilike(pattern, escape="\\"),
        )

        count_statement = (
            select(func.count())
            .select_from(Note)
            .where(search_filter)
        )

        total = session.scalar(count_statement) or 0

        statement = (
            select(Note)
            .where(search_filter)
            .order_by(
                Note.updated_at.desc(),
                Note.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        notes = list(session.scalars(statement).all())

        return notes, total