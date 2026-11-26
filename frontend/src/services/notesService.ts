
import { apiClient } from "./apiClient";

import type {
  Note,
  NoteCreateRequest,
  NoteUpdateRequest,
  NoteListResponse,
  NoteSearchResponse,
} from "../features/notes/notes.types";

export async function getNotes(
  limit = 20,
  offset = 0,
): Promise<NoteListResponse> {
  return apiClient.get<NoteListResponse>(
    `/api/notes?limit=${limit}&offset=${offset}`,
  );
}

export async function getNote(noteId: string): Promise<Note> {
  return apiClient.get<Note>(`/api/notes/${noteId}`);
}

export async function createNote(
  data: NoteCreateRequest,
): Promise<Note> {
  return apiClient.post<Note>("/api/notes", data);
}

export async function updateNote(
  noteId: string,
  data: NoteUpdateRequest,
): Promise<Note> {
  return apiClient.patch<Note>(`/api/notes/${noteId}`, data);
}

export async function deleteNote(noteId: string): Promise<void> {
  return apiClient.delete<void>(`/api/notes/${noteId}`);
}

export async function searchNotes(
  query: string,
  limit = 20,
  offset = 0,
): Promise<NoteSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset),
  });

  return apiClient.get(`/api/notes/search?${params.toString()}`);
}