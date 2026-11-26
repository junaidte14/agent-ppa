import logging

from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from agent import run_agent_turn
from litellm_adapter import LiteLLMAdapter
from llm_interface import LLMClient
from prompts import SYSTEM_PROMPT

from tools.policy import DEFAULT_TOOL_POLICY, ToolPolicy
from tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Application
# ---------------------------------------------------------

app = FastAPI(
    title="Personal Productivity Assistant API",
    description="API interface for the PPA agent.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------
# Web-specific tool policy
# ---------------------------------------------------------

# Any tool requiring human approval is excluded from the
# web application's allowed permissions for this milestone.

APPROVAL_REQUIRED_PERMISSIONS = frozenset(
    tool.required_permission
    for tool in TOOL_REGISTRY.values()
    if tool.requires_approval
)


WEB_TOOL_POLICY = ToolPolicy(
    allowed_permissions=frozenset(
        permission
        for permission in DEFAULT_TOOL_POLICY.allowed_permissions
        if permission not in APPROVAL_REQUIRED_PERMISSIONS
    )
)

# ---------------------------------------------------------
# API schemas
# ---------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000
    )

    conversation_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be empty.")

        return value

class ChatResponse(BaseModel):
    conversation_id: UUID
    reply: str

# ---------------------------------------------------------
# Conversation state
# ---------------------------------------------------------

@dataclass
class ConversationState:
    messages: list[dict[str, Any]]
    lock: Lock = field(default_factory=Lock)

class ConversationStore:

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

        self._conversations: dict[
            UUID,
            ConversationState
        ] = {}

        self._lock = Lock()

    def get_or_create(
        self,
        conversation_id: UUID
    ) -> ConversationState:

        with self._lock:

            conversation = self._conversations.get(
                conversation_id
            )

            if conversation is None:

                conversation = ConversationState(
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_prompt
                        }
                    ]
                )

                self._conversations[conversation_id] = (
                    conversation
                )

            return conversation

conversation_store = ConversationStore(
    system_prompt=SYSTEM_PROMPT
)

# ---------------------------------------------------------
# Dependencies
# ---------------------------------------------------------

def get_llm() -> LLMClient:
    return LiteLLMAdapter()


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.get("/api/health")
def health_check():

    return {
        "status": "healthy",
        "application": "Personal Productivity Assistant",
        "version": "1.0.0",
    }


# ---------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------

@app.post(
    "/api/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    llm: LLMClient = Depends(get_llm)
):

    conversation_id = (
        request.conversation_id or uuid4()
    )

    conversation = conversation_store.get_or_create(
        conversation_id
    )

    with conversation.lock:

        # Save the current history length.
        previous_history_length = len(
            conversation.messages
        )

        # Add the new user message.
        conversation.messages.append({
            "role": "user",
            "content": request.message
        })

        try:

            # Reuse the existing agent implementation.
            #
            # Approval-required tools are blocked by the
            # web-specific policy.
            #
            # approval_callback=None is an additional
            # fail-closed safeguard: the API cannot invoke
            # the CLI's input() approval handler.

            answer = run_agent_turn(
                llm=llm,
                messages=conversation.messages,
                policy=WEB_TOOL_POLICY,
                approval_callback=None
            )

        except Exception as error:

            # Remove the incomplete turn from conversation history.
            del conversation.messages[
                previous_history_length:
            ]

            logger.exception(
                "Agent failed while processing conversation %s",
                conversation_id
            )

            raise HTTPException(
                status_code=502,
                detail=(
                    "The assistant could not complete "
                    "your request. Please try again."
                )
            ) from error

        return ChatResponse(
            conversation_id=conversation_id,
            reply=answer
        )