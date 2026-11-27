
import { MessageSquare } from "lucide-react";

import type { ConversationSummary } from "../../services/conversationService";

interface Props {
  conversations: ConversationSummary[];
  activeConversationId?: string;
  isLoading: boolean;
  error: string | null;
  onSelect: (conversationId: string) => void;
}

export default function ConversationList({
  conversations,
  activeConversationId,
  isLoading,
  error,
  onSelect,
}: Props) {
  return (
    <aside className="conversation-history">
      <div className="conversation-history-header">
        <h2>History</h2>
        <span>{conversations.length}</span>
      </div>

      {error && (
        <p className="conversation-history-error" role="alert">
          {error}
        </p>
      )}

      {isLoading ? (
        <p className="conversation-history-message">
          Loading conversations...
        </p>
      ) : conversations.length === 0 ? (
        <div className="conversation-history-empty">
          <MessageSquare size={22} />
          <p>No conversations yet.</p>
        </div>
      ) : (
        <div className="conversation-history-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              className={`conversation-history-item ${
                activeConversationId === conversation.id
                  ? "conversation-history-item-active"
                  : ""
              }`}
              onClick={() => onSelect(conversation.id)}
              disabled={activeConversationId === conversation.id}
              title={conversation.title}
            >
              <MessageSquare size={16} />

              <span>{conversation.title}</span>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
