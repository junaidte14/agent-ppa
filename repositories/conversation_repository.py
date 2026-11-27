
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from database.models import Conversation, ConversationMessage


class ConversationRepository:
    """
    Handles database operations for conversations and their messages.

    The caller owns the session and transaction.
    This repository never commits, rolls back, or closes sessions.
    """

    @staticmethod
    def create(
        session: Session,
        title: str = "New conversation",
    ) -> Conversation:
        conversation = Conversation(title=title)

        session.add(conversation)
        session.flush()
        session.refresh(conversation)

        return conversation

    @staticmethod
    def get_by_id(
        session: Session,
        conversation_id: UUID,
    ) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id
        )

        return session.scalar(statement)

    @staticmethod
    def list_conversations(
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        statement = (
            select(Conversation)
            .order_by(
                Conversation.updated_at.desc(),
                Conversation.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(session.scalars(statement).all())

    @staticmethod
    def update_title(
        session: Session,
        conversation: Conversation,
        title: str,
    ) -> Conversation:
        conversation.title = title
        conversation.updated_at = func.now()

        session.flush()
        session.refresh(conversation)

        return conversation

    @staticmethod
    def delete(
        session: Session,
        conversation: Conversation,
    ) -> None:
        session.delete(conversation)
        session.flush()

    @staticmethod
    def add_message(
        session: Session,
        conversation_id: UUID,
        message_data: dict[str, Any],
    ) -> ConversationMessage:
        role = message_data.get("role")

        if not isinstance(role, str) or not role:
            raise ValueError("Message must contain a valid role.")

        content = message_data.get("content")

        if content is not None and not isinstance(content, str):
            raise ValueError("Message content must be a string or None.")

        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_data=dict(message_data),
        )

        session.add(message)

        # Update conversation activity whenever a message is added.
        session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )

        session.flush()
        session.refresh(message)

        return message

    @staticmethod
    def list_messages(
        session: Session,
        conversation_id: UUID,
    ) -> list[ConversationMessage]:
        statement = (
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id
            )
            .order_by(ConversationMessage.message_order.asc())
        )

        return list(session.scalars(statement).all())

    @staticmethod
    def count_conversations(session: Session) -> int:
        statement = select(func.count()).select_from(Conversation)

        return session.scalar(statement) or 0
