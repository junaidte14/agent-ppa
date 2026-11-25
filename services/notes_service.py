from typing import Callable
from uuid import UUID
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from repositories.notes_repository import NotesRepository

class NotesService:
    """
    Application service for note management.

    This service owns SQLAlchemy sessions and transactions.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal
    ):
        self.session_factory = session_factory

    @staticmethod
    def _validate_title(title: str) -> str:
        if not isinstance(title, str):
            raise ValueError("title must be a string.")

        title = title.strip()

        if not title:
            raise ValueError("title must not be empty.")

        if len(title) > 255:
            raise ValueError("title must not exceed 255 characters")

        return title

    @staticmethod
    def _validate_content(content: str) -> str:
        if not isinstance(content, str):
            raise ValueError("content must be a string.")

        if not content.strip():
            raise ValueError("content must not be empty.")

        return content

    @staticmethod
    def _serialize(note) -> dict:
        return {
            "id": str(note.id),
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat()
        }

    def create_note(
        self,
        title: str,
        content: str
    ) -> dict:
        
        title = self._validate_title(title=title)
        content = self._validate_content(content=content)

        with self.session_factory() as session:
            with session.begin():
                note = NotesRepository.create(
                    session=session,
                    title=title,
                    content=content
                )

                result = self._serialize(note)
                
            return result

    def get_note(
        self,
        note_id
    ) -> dict | None:
        with self.session_factory() as session:
            note = NotesRepository.get_by_id(
                session=session,
                note_id=note_id
            )
            if note is None:
                return None
            return self._serialize(note=note)

    def update_note(
        self,
        note_id: UUID,
        title: str | None = None,
        content: str | None = None,
    ) -> dict | None:
        
        if title is None and content is None:
            raise ValueError("At least one of title or content must be supplied.")

        if title is not None:
            title = self._validate_title(title)

        if content is not None:
            content = self._validate_content(content)

        with self.session_factory() as session:
            with session.begin():
                note = NotesRepository.get_by_id(
                    session=session,
                    note_id=note_id,
                )

                if note is None:
                    return None
                
                note = NotesRepository.update(
                    session=session,
                    note=note,
                    title=title,
                    content=content
                )

                result = self._serialize(note)
            
            return result

    def delete_note(
        self,
        note_id: UUID
    ) -> bool:

        with self.session_factory() as session:
            with session.begin():

                note = NotesRepository.get_by_id(session=session, note_id=note_id)
                if note is None:
                    return False
                NotesRepository.delete(
                    session=session,
                    note=note
                )

            return True

notes_service = NotesService()