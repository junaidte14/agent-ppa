
import { useState, type SubmitEvent } from "react";
import {
  Check,
  MessageSquare,
  Pencil,
  Trash2,
  X,
} from "lucide-react";

import type { ConversationSummary } from "../../services/conversationService";

interface Props {
  conversations: ConversationSummary[];
  activeConversationId?: string;
  isLoading: boolean;
  error: string | null;
  totalConversations: number;
  isLoadingMore: boolean;
  onLoadMore: () => void;
  onSelect: (conversationId: string) => void;
  onRename: (conversationId: string, title: string) => Promise<boolean>;
  onDelete: (conversationId: string) => Promise<boolean>;
}

export default function ConversationList({
  conversations,
  activeConversationId,
  isLoading,
  error,
  onSelect,
  onRename,
  onDelete,
  totalConversations,
  isLoadingMore,
  onLoadMore,
}: Props) {
  const [editingConversationId, setEditingConversationId] = useState<
    string | null
  >(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null,
  );
  const [isDeleting, setIsDeleting] = useState(false);

  function startEditing(conversation: ConversationSummary) {
    setConfirmingDeleteId(null);
    setEditingConversationId(conversation.id);
    setDraftTitle(conversation.title);
  }

  function cancelEditing() {
    setEditingConversationId(null);
    setDraftTitle("");
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!editingConversationId || isSaving) {
      return;
    }

    const title = draftTitle.trim();

    if (!title) {
      return;
    }

    const currentConversation = conversations.find(
      (conversation) => conversation.id === editingConversationId,
    );

    if (!currentConversation) {
      cancelEditing();
      return;
    }

    if (title === currentConversation.title) {
      cancelEditing();
      return;
    }

    setIsSaving(true);

    try {
      const succeeded = await onRename(editingConversationId, title);

      if (succeeded) {
        cancelEditing();
      }
    } finally {
      setIsSaving(false);
    }
  }

  function startDeleteConfirmation(conversationId: string) {
    cancelEditing();
    setConfirmingDeleteId(conversationId);
  }

  async function handleConfirmDelete() {
    if (!confirmingDeleteId || isDeleting) {
      return;
    }

    setIsDeleting(true);

    try {
      const succeeded = await onDelete(confirmingDeleteId);

      if (succeeded) {
        setConfirmingDeleteId(null);
      }
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <aside className="conversation-history">
      <div className="conversation-history-header">
        <h2>History</h2>
        <span>{totalConversations}</span>
      </div>

      {error && (
        <p className="conversation-history-error" role="alert">
          {error}
        </p>
      )}

      {isLoading ? (
        <p>Loading conversations...</p>
      ) : conversations.length === 0 ? (
        <div>No conversations yet.</div>
      ) : (
        <>
        <div className="conversation-history-list">
          {conversations.map((conversation) => {
            const isEditing =
              editingConversationId === conversation.id;

            const isActive =
              activeConversationId === conversation.id;

            const isConfirmingDelete =
              confirmingDeleteId === conversation.id;

            return (
              <div
                key={conversation.id}
                className={`conversation-history-row ${
                  isActive ? "active" : ""
                }`}
              >
                {isEditing ? (
                  <form
                    className="conversation-rename-form"
                    onSubmit={handleSubmit}
                  >
                    <input
                      autoFocus
                      type="text"
                      value={draftTitle}
                      maxLength={255}
                      aria-label="Conversation title"
                      onChange={(event) =>
                        setDraftTitle(event.target.value)
                      }
                      disabled={isSaving}
                    />

                    <button
                      type="submit"
                      className="conversation-action-button"
                      title="Save title"
                      aria-label="Save title"
                      disabled={isSaving || !draftTitle.trim()}
                    >
                      <Check size={16} />
                    </button>

                    <button
                      type="button"
                      className="conversation-action-button"
                      title="Cancel editing"
                      aria-label="Cancel editing"
                      onClick={cancelEditing}
                      disabled={isSaving}
                    >
                      <X size={16} />
                    </button>
                  </form>
                ) : (
                  <>
                    <button
                      type="button"
                      className={`conversation-history-item ${
                        isActive ? "active" : ""
                      }`}
                      onClick={() => onSelect(conversation.id)}
                      disabled={isActive || isConfirmingDelete}
                      title={conversation.title}
                    >
                      <MessageSquare size={16} />
                      <span>{conversation.title}</span>
                    </button>

                    {isConfirmingDelete ? (
                      <div className="conversation-delete-confirm">
                        <span>Delete?</span>

                        <button
                          type="button"
                          className="conversation-action-button conversation-delete-confirm-button"
                          title="Confirm deletion"
                          aria-label="Confirm deletion"
                          onClick={handleConfirmDelete}
                          disabled={isDeleting}
                        >
                          <Check size={16} />
                        </button>

                        <button
                          type="button"
                          className="conversation-action-button"
                          title="Cancel deletion"
                          aria-label="Cancel deletion"
                          onClick={() => setConfirmingDeleteId(null)}
                          disabled={isDeleting}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="conversation-action-button"
                          title="Rename conversation"
                          aria-label={`Rename ${conversation.title}`}
                          onClick={() => startEditing(conversation)}
                        >
                          <Pencil size={15} />
                        </button>

                        <button
                          type="button"
                          className="conversation-action-button conversation-delete-button"
                          title="Delete conversation"
                          aria-label={`Delete ${conversation.title}`}
                          onClick={() =>
                            startDeleteConfirmation(conversation.id)
                          }
                        >
                          <Trash2 size={15} />
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
        {conversations.length < totalConversations && (
            <button
                type="button"
                className="conversation-load-more"
                onClick={onLoadMore}
                disabled={isLoadingMore}
            >
                {isLoadingMore ? "Loading..." : "Load more"}
            </button>
        )}
        </>
      )}
    </aside>
  );
}
