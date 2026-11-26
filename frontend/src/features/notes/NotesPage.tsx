import { useEffect, useState } from "react";

import {
  createNote,
  getNotes,
  updateNote,
  deleteNote,
  searchNotes,
} from "../../services/notesService";

import type {
  Note,
  NoteCreateRequest,
} from "./notes.types";

import NoteList from "./NoteList";
import NoteEditor from "./NoteEditor";

import "../../styles/notes.css";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 350;

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [selectedNote, setSelectedNote] = useState<Note | null>(null);

  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);

  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [refreshVersion, setRefreshVersion] = useState(0);

  // Debounce search input before making API requests.
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [searchInput]);

  useEffect(() => {
    let active = true;

    async function fetchNotes() {
      setLoading(true);
      setError(null);

      try {
        const response = debouncedQuery
          ? await searchNotes(debouncedQuery, PAGE_SIZE, offset)
          : await getNotes(PAGE_SIZE, offset);

        if (!active) return;

        setNotes(response.notes);
        setTotal(response.total);

        setSelectedNote((current) => {
          if (!current) return null;

          return (
            response.notes.find((note) => note.id === current.id) ?? null
          );
        });
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error ? err.message : "Failed to load notes.",
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void fetchNotes();

    return () => {
      active = false;
    };
  }, [debouncedQuery, offset, refreshVersion]);

  function handleSearchChange(value: string) {
    setSearchInput(value);
    setOffset(0);

    setSelectedNote(null);
    setIsCreating(false);
    setIsEditing(false);
    setSaveError(null);
    setDeleteError(null);
  }

  function handleNewNote() {
    setSelectedNote(null);
    setIsEditing(false);
    setSaveError(null);
    setDeleteError(null);
    setIsCreating(true);
  }

  function handleCancelEditor() {
    setIsCreating(false);
    setIsEditing(false);
    setSaveError(null);
  }

  async function handleCreateNote(data: NoteCreateRequest) {
    setSaving(true);
    setSaveError(null);

    try {
        const createdNote = await createNote(data);

        setSelectedNote(createdNote);
        setIsCreating(false);

        // Return to the unfiltered first page.
        setSearchInput("");
        setDebouncedQuery("");
        setOffset(0);

        setRefreshVersion((current) => current + 1);

    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to create note.",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleEditNote() {
    if (!selectedNote) return;

    setIsCreating(false);
    setSaveError(null);
    setIsEditing(true);
  }

  async function handleUpdateNote(data: NoteCreateRequest) {
    if (!selectedNote) return;

    setSaving(true);
    setSaveError(null);

    try {
        const updatedNote = await updateNote(selectedNote.id, data);

        setSelectedNote(updatedNote);
        setIsEditing(false);

        setRefreshVersion((current) => current + 1);

    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to update note.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteNote() {
    if (!selectedNote) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete "${selectedNote.title}"? This action cannot be undone.`,
    );

    if (!confirmed) return;

    setIsDeleting(true);
    setDeleteError(null);

    try {
        await deleteNote(selectedNote.id);

        setSelectedNote(null);
        setIsCreating(false);
        setIsEditing(false);

        // If this was the only note on the current page,
        // move back to the previous page.
        if (notes.length === 1 && offset > 0) {
            setOffset((current) => Math.max(0, current - PAGE_SIZE));
        }

        setRefreshVersion((current) => current + 1);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete note.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  const hasPreviousPage = offset > 0;
  const hasNextPage = offset + notes.length < total;

  const firstVisibleNote = total === 0 ? 0 : offset + 1;
  const lastVisibleNote = Math.min(offset + notes.length, total);

  return (
    <section className="notes-page">
      <header className="notes-header">
        <div>
          <p className="eyebrow">YOUR WORKSPACE</p>
          <h1>Notes</h1>
          <p>Capture and organize your thoughts.</p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={handleNewNote}
        >
          + New Note
        </button>
      </header>

      <div className="notes-search">
        <input
          type="search"
          value={searchInput}
          onChange={(event) => handleSearchChange(event.target.value)}
          placeholder="Search notes..."
          aria-label="Search notes"
        />

        {searchInput && (
          <button
            type="button"
            className="secondary-button"
            onClick={() => handleSearchChange("")}
          >
            Clear
          </button>
        )}
      </div>

      {loading && <p>Loading notes...</p>}

      {error && (
        <div className="notes-error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            onClick={() => setRefreshVersion((current) => current + 1)}
            >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="notes-workspace">
            <NoteList
              notes={notes}
              selectedNoteId={selectedNote?.id ?? null}
              onSelect={(note) => {
                setSelectedNote(note);
                setIsCreating(false);
                setIsEditing(false);
                setSaveError(null);
                setDeleteError(null);
              }}
            />

            <div className="notes-detail">
              {isCreating ? (
                <NoteEditor
                  key="new-note"
                  onSave={handleCreateNote}
                  onCancel={handleCancelEditor}
                  saving={saving}
                  error={saveError}
                />
              ) : isEditing && selectedNote ? (
                <NoteEditor
                  key={selectedNote.id}
                  initialNote={selectedNote}
                  onSave={handleUpdateNote}
                  onCancel={handleCancelEditor}
                  saving={saving}
                  error={saveError}
                />
              ) : selectedNote ? (
                <>
                  <div className="notes-detail-header">
                    <h2>{selectedNote.title}</h2>

                    <div className="note-detail-actions">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleEditNote}
                      >
                        Edit Note
                      </button>

                      <button
                        type="button"
                        className="danger-button"
                        onClick={() => void handleDeleteNote()}
                        disabled={isDeleting}
                      >
                        {isDeleting ? "Deleting..." : "Delete Note"}
                      </button>
                    </div>
                  </div>

                  {deleteError && (
                    <div className="notes-error" role="alert">
                      {deleteError}
                    </div>
                  )}

                  <p>{selectedNote.content}</p>
                </>
              ) : (
                <div className="notes-detail-empty">
                  <h2>Select a note</h2>
                  <p>
                    Choose a note from the list or create a new one.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="notes-pagination">
            <span>
              Showing {firstVisibleNote}–{lastVisibleNote} of {total} notes
            </span>

            <div className="notes-pagination-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={!hasPreviousPage}
                onClick={() =>
                  setOffset((current) => Math.max(0, current - PAGE_SIZE))
                }
              >
                Previous
              </button>

              <button
                type="button"
                className="secondary-button"
                disabled={!hasNextPage}
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
