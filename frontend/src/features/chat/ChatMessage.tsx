import type { ChatMessage as ChatMessageType } from "./chat.types";

interface Props {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={`chat-message-row ${
        isUser ? "chat-message-row-user" : "chat-message-row-assistant"
      }`}
    >
      <div
        className={`chat-message-bubble ${
          isUser ? "chat-message-user" : "chat-message-assistant"
        }`}
      >
        <div className="chat-message-role">
          {isUser ? "You" : "PPA Assistant"}
        </div>
        <div className="chat-message-content">
          {message.content}
        </div>
      </div>
    </div>
  );
}
