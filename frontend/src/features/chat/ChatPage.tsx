
import { useEffect, useRef, useState } from "react";
import { MessageSquare, Plus } from "lucide-react";

import {
  getConversation,
  getConversations,
  renameConversation,
  deleteConversation,
  type ConversationMessage,
  type ConversationSummary,
} from "../../services/conversationService";

import { sendChatMessage } from "../../services/chatService";
import type { ChatMessage as ChatMessageType } from "./chat.types";

import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import ConversationList from "./ConversationList";

function createMessage(
  role: ChatMessageType["role"],
  content: string,
): ChatMessageType {
  return {
    id: crypto.randomUUID(),
    role,
    content,
  };
}

function toChatMessages(
  conversationMessages: ConversationMessage[],
): ChatMessageType[] {
  return [...conversationMessages]
    .sort((a, b) => a.message_order - b.message_order)
    .filter(
      (message) =>
        message.role === "user" || message.role === "assistant",
    )
    .map((message) => {
      const storedContent = message.message_data.content;

      const content =
        typeof message.content === "string"
          ? message.content
          : typeof storedContent === "string"
            ? storedContent
            : "";

      return {
        id: message.id,
        role: message.role as ChatMessageType["role"],
        content,
      };
    })
    .filter((message) => message.content.trim().length > 0);
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [conversationId, setConversationId] = useState<string>();

  const [conversations, setConversations] = useState<
    ConversationSummary[]
  >([]);

  const [isLoadingConversations, setIsLoadingConversations] =
    useState(true);

  const [isLoadingConversation, setIsLoadingConversation] =
    useState(false);

  const [isSending, setIsSending] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [totalConversations, setTotalConversations] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Prevent an older conversation request from replacing a newer selection.
  const conversationRequestId = useRef(0);

  async function refreshConversations() {
    try {
      const result = await getConversations(20, 0);

      setConversations(result.items);
      setTotalConversations(result.total);
      setHistoryError(null);
    } catch (err) {
      setHistoryError(
        err instanceof Error
          ? err.message
          : "Could not load conversation history.",
      );
    }
  }

  // Load saved conversations when the Chat page opens.
  useEffect(() => {
    let active = true;

    async function loadConversations() {
      try {
        const result = await getConversations(20, 0);

        if (!active) return;

        setConversations(result.items);
        setTotalConversations(result.total);
        setHistoryError(null);
      } catch (err) {
        if (!active) return;

        setHistoryError(
          err instanceof Error
            ? err.message
            : "Could not load conversation history.",
        );
      } finally {
        if (active) {
          setIsLoadingConversations(false);
        }
      }
    }

    void loadConversations();

    return () => {
      active = false;
    };
  }, []);

  async function handleLoadMoreConversations() {
    if (
      isLoadingMore ||
      conversations.length >= totalConversations
    ) {
      return;
    }

    setIsLoadingMore(true);
    setHistoryError(null);

    try {
      const result = await getConversations(20, conversations.length);

      // Append results while avoiding duplicate conversation IDs.
      setConversations((current) => {
        const existingIds = new Set(
          current.map((conversation) => conversation.id),
        );

        const newItems = result.items.filter(
          (conversation) => !existingIds.has(conversation.id),
        );

        return [...current, ...newItems];
      });

      setTotalConversations(result.total);
    } catch (err) {
      setHistoryError(
        err instanceof Error
          ? err.message
          : "Could not load more conversations.",
      );
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleSelectConversation(
    selectedConversationId: string,
  ) {
    if (isSending || isLoadingConversation) return;
    if (selectedConversationId === conversationId) return;

    const requestId = ++conversationRequestId.current;

    setIsLoadingConversation(true);
    setError(null);

    try {
      const conversation = await getConversation(
        selectedConversationId,
      );

      // Ignore the response if another selection was made meanwhile.
      if (requestId !== conversationRequestId.current) return;

      setConversationId(conversation.id);
      setMessages(toChatMessages(conversation.messages));
    } catch (err) {
      if (requestId === conversationRequestId.current) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not load this conversation.",
        );
      }
    } finally {
      if (requestId === conversationRequestId.current) {
        setIsLoadingConversation(false);
      }
    }
  }

  async function handleSend(message: string) {
    if (isSending || isLoadingConversation) return;

    setError(null);

    setMessages((current) => [
      ...current,
      createMessage("user", message),
    ]);

    setIsSending(true);

    try {
      const response = await sendChatMessage({
        message,
        ...(conversationId
          ? { conversation_id: conversationId }
          : {}),
      });

      setConversationId(response.conversation_id);

      setMessages((current) => [
        ...current,
        createMessage("assistant", response.reply),
      ]);

      await refreshConversations();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while contacting the assistant.",
      );

      // The backend may have persisted the user message even if
      // the assistant request failed.
      await refreshConversations();
    } finally {
      setIsSending(false);
    }
  }

  async function handleDeleteConversation(
    deletedId: string,
  ): Promise<boolean> {
    if (isSending || isLoadingConversation) {
      return false;
    }

    setHistoryError(null);

    try {
      await deleteConversation(deletedId);

      setConversations((current) =>
        current.filter(
          (conversation) => conversation.id !== deletedId,
        ),
      );

      if (deletedId === conversationId) {
        conversationRequestId.current += 1;
        setConversationId(undefined);
        setMessages([]);
        setError(null);
        setTotalConversations((current) => Math.max(0, current - 1));
        setIsLoadingConversation(false);
      }

      return true;
    } catch (err) {
      setHistoryError(
        err instanceof Error
          ? err.message
          : "Could not delete the conversation.",
      );

      return false;
    }
  }

  async function handleRenameConversation(
    conversationId: string,
    title: string,
  ): Promise<boolean> {
    setHistoryError(null);

    try {
      const updatedConversation = await renameConversation(
        conversationId,
        title,
      );

      setConversations((current) =>
        current
          .map((conversation) =>
            conversation.id === conversationId
              ? updatedConversation
              : conversation,
          )
          .sort(
            (a, b) =>
              new Date(b.updated_at).getTime() -
              new Date(a.updated_at).getTime(),
          ),
      );

      return true;
    } catch (err) {
      setHistoryError(
        err instanceof Error
          ? err.message
          : "Could not rename the conversation.",
      );

      return false;
    }
  }

  function startNewConversation() {
    if (isSending || isLoadingConversation) return;

    // Invalidate any conversation-loading request still in progress.
    conversationRequestId.current += 1;

    setMessages([]);
    setConversationId(undefined);
    setError(null);
    setIsLoadingConversation(false);
  }

  return (
    <section className="chat-page">
      <header className="chat-header">
        <div>
          <h1>Chat</h1>
          <p>Work with your Personal Productivity Assistant.</p>
        </div>

        <button
          className="chat-new-button"
          onClick={startNewConversation}
          disabled={isSending || isLoadingConversation}
        >
          <Plus size={17} />
          New conversation
        </button>
      </header>

      <div className="chat-workspace">
        <ConversationList
          conversations={conversations}
          activeConversationId={conversationId}
          isLoading={isLoadingConversations}
          error={historyError}
          onSelect={handleSelectConversation}
          onRename={handleRenameConversation}
          onDelete={handleDeleteConversation}
          totalConversations={totalConversations}
          isLoadingMore={isLoadingMore}
          onLoadMore={handleLoadMoreConversations}
        />

        <div className="chat-panel">
          <div className="chat-messages">
            {isLoadingConversation ? (
              <div className="chat-empty-state">
                <p>Loading conversation...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="chat-empty-state">
                <div className="chat-empty-icon">
                  <MessageSquare size={27} />
                </div>
                <h2>How can I help you?</h2>
                <p>
                  Ask a question, analyze text, or work with your notes.
                </p>
              </div>
            ) : (
              messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))
            )}

            {isSending && (
              <div className="chat-typing-indicator">
                PPA Assistant is thinking...
              </div>
            )}
          </div>

          {error && (
            <div className="chat-error" role="alert">
              {error}
            </div>
          )}

          <div className="chat-composer">
            <ChatInput
              onSend={handleSend}
              disabled={isSending || isLoadingConversation}
            />
            <p className="chat-disclaimer">
              The assistant can make mistakes. Verify important actions.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
