from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from uuid import UUID

class CalculatorInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", 
        strict=True
    )
    
    expression: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "A mathematical expression, for example "
            "(125 * 8) + 450"
        )
    )

class DateTimeInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True
    )
    
class TextAnalyzerInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True
    )

    text: str = Field(
        description="The text to analyze."
    )

class MessageInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True
    )

    recipient: str = Field(
        min_length=1,
        description="The intended message recipient."
    )

    message: str = Field(
        min_length=1,
        max_length=1000,
        description="The message to send."
    )

class CreateNoteInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    title: str = Field(
        min_length=1,
        max_length=255,
        description="A short title for the note.",
    )

    content: str = Field(
        min_length=1,
        description="The full content of the note.",
    )


class GetNoteInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    note_id: UUID = Field(
        description="The UUID of the note to retrieve.",
    )


class UpdateNoteInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    note_id: UUID = Field(
        description="The UUID of the note to update.",
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="The new note title, if changing it.",
    )

    content: str | None = Field(
        default=None,
        min_length=1,
        description="The new note content, if changing it.",
    )

    @model_validator(mode="after")
    def require_an_update(self):
        if self.title is None and self.content is None:
            raise ValueError(
                "At least one of title or content must be supplied."
            )

        return self


class DeleteNoteInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    note_id: UUID = Field(
        description="The UUID of the note to delete.",
    )

class ListNotesInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchNotesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("query")
    @classmethod
    def validate_query_not_blank(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Search query cannot be empty or whitespace.")

        return value