
import logging

from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from agent import run_agent_turn
from api.dependencies.chat import get_llm, WEB_TOOL_POLICY
from api.schemas.chat import ChatRequest, ChatResponse
from llm_interface import LLMClient
from prompts import SYSTEM_PROMPT
from services.conversation_service import conversation_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Chat"],
)

# Process-local coordination for concurrent requests to the same
# conversation. This is not a distributed lock.
_conversation_locks: dict[UUID, Lock] = {}
_locks_guard = Lock()


def get_conversation_lock(conversation_id: UUID) -> Lock:
    with _locks_guard:
        if conversation_id not in _conversation_locks:
            _conversation_locks[conversation_id] = Lock()

        return _conversation_locks[conversation_id]



@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    llm: LLMClient = Depends(get_llm),
):
    # Create a new conversation if no ID was supplied.
    if request.conversation_id is None:
        try:
            conversation = conversation_service.create_conversation()
            conversation_id = UUID(conversation["id"])
        except Exception as error:
            logger.exception("Could not create conversation.")
            raise HTTPException(
                status_code=500,
                detail="Could not create a conversation.",
            ) from error
    else:
        conversation_id = request.conversation_id

    conversation_lock = get_conversation_lock(conversation_id)

    with conversation_lock:

        # Load history only after acquiring the lock.
        try:
            conversation = conversation_service.get_conversation(
                conversation_id
            )
        except Exception as error:
            logger.exception(
                "Could not load conversation %s",
                conversation_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Could not load the conversation.",
            ) from error

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        persisted_messages = conversation["messages"]

        # Reconstruct the agent's message history.
        # The system prompt is supplied at runtime, not persisted.
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        messages.extend(
            message["message_data"]
            for message in persisted_messages
        )

        # Persist the user message before calling the LLM.
        user_message = {
            "role": "user",
            "content": request.message,
        }

        try:
            conversation_service.append_messages(
                conversation_id,
                [user_message],
            )
        except Exception as error:
            logger.exception(
                "Could not persist user message for conversation %s",
                conversation_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Could not save your message.",
            ) from error

        messages.append(user_message)

        # Track messages generated during this agent turn.
        generated_messages_start = len(messages)

        try:
            answer = run_agent_turn(
                llm=llm,
                messages=messages,
                policy=WEB_TOOL_POLICY,
                approval_callback=None,
            )
        except Exception as error:
            # Preserve partial history because a tool may already
            # have executed before the failure.
            generated_messages = messages[generated_messages_start:]

            if generated_messages:
                try:
                    conversation_service.append_messages(
                        conversation_id,
                        generated_messages,
                    )
                except Exception:
                    logger.exception(
                        "Could not persist partial agent history "
                        "for conversation %s",
                        conversation_id,
                    )

            logger.exception(
                "Agent failed while processing conversation %s",
                conversation_id,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "The assistant could not complete your request. "
                    "Please try again."
                ),
            ) from error

        # Persist assistant messages, tool calls, and tool results.
        generated_messages = messages[generated_messages_start:]

        if generated_messages:
            try:
                conversation_service.append_messages(
                    conversation_id,
                    generated_messages,
                )
            except Exception as error:
                logger.exception(
                    "Could not persist agent response for conversation %s",
                    conversation_id,
                )
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "The assistant responded, but the conversation "
                        "could not be saved."
                    ),
                ) from error

        return ChatResponse(
            conversation_id=conversation_id,
            reply=answer,
        )
