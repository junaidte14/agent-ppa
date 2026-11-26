
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateNoteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class UpdateNoteRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError(
                "At least one of title or content must be supplied."
            )

        if self.title is None and self.content is None:
            raise ValueError(
                "At least one of title or content must be non-null."
            )

        return self


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
    total: int
    limit: int
    offset: int


class NoteSearchResponse(NoteListResponse):
    query: str


class DeleteNoteResponse(BaseModel):
    deleted: bool
