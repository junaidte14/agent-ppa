
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import sessionmaker

from database.connection import SessionLocal
from database.models import Conversation, ConversationMessage
from repositories.conversation_repository import ConversationRepository


class ConversationService:
    """
    Application service for conversation persistence.

    Owns database sessions and transaction boundaries.
    Delegates database operations to ConversationRepository.
    """

    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
    ):
        self.session_factory = session_factory

    @staticmethod
    def _serialize_conversation(
        conversation: Conversation,
    ) -> dict[str, Any]:
        return {
            "id": str(conversation.id),
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }

    @staticmethod
    def _serialize_message(
        message: ConversationMessage,
    ) -> dict[str, Any]:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "message_order": message.message_order,
            "role": message.role,
            "content": message.content,
            "message_data": message.message_data,
            "created_at": message.created_at.isoformat(),
        }

    @staticmethod
    def _validate_title(title: str) -> str:
        if not isinstance(title, str):
            raise ValueError("Conversation title must be a string.")

        title = title.strip()

        if not title:
            raise ValueError("Conversation title cannot be empty.")

        if len(title) > 255:
            raise ValueError(
                "Conversation title cannot exceed 255 characters."
            )

        return title

    @staticmethod
    def _normalize_message(
        message: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise ValueError("Each message must be a dictionary.")

        role = message.get("role")

        if not isinstance(role, str) or not role.strip():
            raise ValueError("Message must contain a valid role.")

        if len(role) > 30:
            raise ValueError("Message role cannot exceed 30 characters.")

        content = message.get("content")

        if content is not None and not isinstance(content, str):
            raise ValueError("Message content must be a string or None.")

        try:
            # Ensure the complete message can be stored as PostgreSQL JSONB.
            normalized = json.loads(json.dumps(message))
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Message contains data that cannot be stored as JSON."
            ) from error

        return normalized

    @staticmethod
    def _generate_title(message: str) -> str:
        """Generate a concise conversation title from the first user message."""
        title = " ".join(message.split())

        if len(title) > 60:
            title = title[:57].rstrip() + "..."

        return title
    
    def create_conversation(
        self,
        title: str = "New conversation",
    ) -> dict[str, Any]:
        title = self._validate_title(title)

        with self.session_factory() as session:
            with session.begin():
                conversation = ConversationRepository.create(
                    session=session,
                    title=title,
                )

                result = self._serialize_conversation(conversation)

            return result

    def get_conversation(
        self,
        conversation_id: UUID,
    ) -> dict[str, Any] | None:
        with self.session_factory() as session:
            conversation = ConversationRepository.get_by_id(
                session=session,
                conversation_id=conversation_id,
            )

            if conversation is None:
                return None

            messages = ConversationRepository.list_messages(
                session=session,
                conversation_id=conversation_id,
            )

            return {
                **self._serialize_conversation(conversation),
                "messages": [
                    self._serialize_message(message)
                    for message in messages
                ],
            }

    def list_conversations(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        with self.session_factory() as session:
            total = ConversationRepository.count_conversations(
                session=session,
            )

            conversations = ConversationRepository.list_conversations(
                session=session,
                limit=limit,
                offset=offset,
            )

            return {
                "items": [
                    self._serialize_conversation(conversation)
                    for conversation in conversations
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def rename_conversation(
        self,
        conversation_id: UUID,
        title: str,
    ) -> dict[str, Any] | None:
        title = self._validate_title(title)

        with self.session_factory() as session:
            with session.begin():
                conversation = ConversationRepository.get_by_id(
                    session=session,
                    conversation_id=conversation_id,
                )

                if conversation is None:
                    return None

                conversation = ConversationRepository.update_title(
                    session=session,
                    conversation=conversation,
                    title=title,
                )

                result = self._serialize_conversation(conversation)

            return result

    def delete_conversation(
        self,
        conversation_id: UUID,
    ) -> bool:
        with self.session_factory() as session:
            with session.begin():
                conversation = ConversationRepository.get_by_id(
                    session=session,
                    conversation_id=conversation_id,
                )

                if conversation is None:
                    return False

                ConversationRepository.delete(
                    session=session,
                    conversation=conversation,
                )

            return True

    def append_messages(
        self,
        conversation_id: UUID,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("Messages must be a non-empty list.")

        normalized_messages = [
            self._normalize_message(message)
            for message in messages
        ]

        with self.session_factory() as session:
            with session.begin():
                conversation = ConversationRepository.get_by_id(
                    session=session,
                    conversation_id=conversation_id,
                )

                if conversation is None:
                    raise LookupError("Conversation not found.")

                existing_messages = ConversationRepository.list_messages(
                    session=session,
                    conversation_id=conversation_id,
                )

                # Generate a title only for a new, untouched conversation.
                if (
                    conversation.title == "New conversation"
                    and not existing_messages
                ):
                    first_user_message = next(
                        (
                            message
                            for message in normalized_messages
                            if (
                                message.get("role") == "user"
                                and isinstance(message.get("content"), str)
                                and message["content"].strip()
                            )
                        ),
                        None,
                    )

                    if first_user_message is not None:
                        title = self._generate_title(
                            first_user_message["content"]
                        )

                        ConversationRepository.update_title(
                            session=session,
                            conversation=conversation,
                            title=title,
                        )

                saved_messages = []

                for message in normalized_messages:
                    saved_message = ConversationRepository.add_message(
                        session,
                        conversation_id,
                        message,
                    )

                    saved_messages.append(
                        self._serialize_message(saved_message)
                    )

            return saved_messages

conversation_service = ConversationService()
