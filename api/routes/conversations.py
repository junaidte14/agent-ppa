
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from api.schemas.conversations import (
    ConversationDetail,
    ConversationRenameRequest,
    ConversationSummary,
)
from services.conversation_service import conversation_service


router = APIRouter(
    prefix="/api/conversations",
    tags=["Conversations"],
)


@router.get(
    "",
    response_model=list[ConversationSummary],
)
def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        return conversation_service.list_conversations(
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
def get_conversation(conversation_id: UUID):
    conversation = conversation_service.get_conversation(
        conversation_id
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummary,
)
def rename_conversation(
    conversation_id: UUID,
    request: ConversationRenameRequest,
):
    try:
        conversation = conversation_service.rename_conversation(
            conversation_id=conversation_id,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(conversation_id: UUID):
    deleted = conversation_service.delete_conversation(
        conversation_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
