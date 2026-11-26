
import { useState, type SubmitEvent } from "react";

import type { Note, NoteCreateRequest } from "./notes.types";

interface NoteEditorProps {
  initialNote?: Note | null;
  onSave: (data: NoteCreateRequest) => Promise<void>;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
}

export default function NoteEditor({
  initialNote = null,
  onSave,
  onCancel,
  saving,
  error,
}: NoteEditorProps) {
  const [title, setTitle] = useState(initialNote?.title ?? "");
  const [content, setContent] = useState(initialNote?.content ?? "");

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    await onSave({
      title: title.trim(),
      content,
    });
  }

  const isEditing = initialNote !== null;

  return (
    <form className="note-editor" onSubmit={handleSubmit}>
      <div className="note-editor-header">
        <h2>{isEditing ? "Edit Note" : "New Note"}</h2>
        <p>
          {isEditing
            ? "Update your note."
            : "Capture your thoughts and ideas."}
        </p>
      </div>

      <div className="note-editor-field">
        <label htmlFor="note-title">Title</label>

        <input
          id="note-title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Enter note title"
          maxLength={255}
          required
        />
      </div>

      <div className="note-editor-field">
        <label htmlFor="note-content">Content</label>

        <textarea
          id="note-content"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="Write your note here..."
          rows={12}
          required
        />
      </div>

      {error && (
        <div className="notes-error" role="alert">
          {error}
        </div>
      )}

      <div className="note-editor-actions">
        <button
          type="button"
          className="secondary-button"
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </button>

        <button
          type="submit"
          className="primary-button"
          disabled={saving || !title.trim() || !content.trim()}
        >
          {saving
            ? "Saving..."
            : isEditing
              ? "Save Changes"
              : "Save Note"}
        </button>
      </div>
    </form>
  );
}
