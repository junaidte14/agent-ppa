
import { useState } from "react";
import { MessageSquare, Plus } from "lucide-react";

import { sendChatMessage } from "../../services/chatService";
import type { ChatMessage as ChatMessageType } from "./chat.types";

import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";

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

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(message: string) {
    if (isSending) return;

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
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while contacting the assistant.",
      );
    } finally {
      setIsSending(false);
    }
  }

  function startNewConversation() {
    if (isSending) return;

    setMessages([]);
    setConversationId(undefined);
    setError(null);
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
          disabled={isSending}
        >
          <Plus size={17} />
          New conversation
        </button>
      </header>

      <div className="chat-panel">
        <div className="chat-messages">
          {messages.length === 0 ? (
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
          <ChatInput onSend={handleSend} disabled={isSending} />
          <p className="chat-disclaimer">
            The assistant can make mistakes. Verify important actions.
          </p>
        </div>
      </div>
    </section>
  );
}
