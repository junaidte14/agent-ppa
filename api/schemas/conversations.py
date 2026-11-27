
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    message_order: int
    role: str
    content: str | None
    message_data: dict[str, Any]
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessageResponse]


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Conversation title cannot be empty.")

        return value

class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int