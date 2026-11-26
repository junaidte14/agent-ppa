
import type { Note } from "./notes.types";

interface NoteListProps {
  notes: Note[];
  selectedNoteId: string | null;
  onSelect: (note: Note) => void;
}

export default function NoteList({
  notes,
  selectedNoteId,
  onSelect,
}: NoteListProps) {
  if (notes.length === 0) {
    return (
      <div className="notes-empty">
        <h3>No notes found.</h3>
        <p>Create your first note to get started.</p>
      </div>
    );
  }

  return (
    <div className="notes-list">
      {notes.map((note) => (
        <button
          key={note.id}
          type="button"
          className={`note-list-item ${
            selectedNoteId === note.id ? "active" : ""
          }`}
          onClick={() => onSelect(note)}
        >
          <h3>{note.title}</h3>

          <p>
            {note.content.length > 100
              ? `${note.content.slice(0, 100)}...`
              : note.content}
          </p>

          <span>
            {new Date(note.updated_at).toLocaleDateString()}
          </span>
        </button>
      ))}
    </div>
  );
}
