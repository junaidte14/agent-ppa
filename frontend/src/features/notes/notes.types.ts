
export interface Note {
  id: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface NoteCreateRequest {
  title: string;
  content: string;
}

export interface NoteUpdateRequest {
  title?: string;
  content?: string;
}

export interface NoteListResponse {
  notes: Note[];
  total: number;
  limit: number;
  offset: number;
}

export interface NoteSearchResponse {
  query: string;
  notes: Note[];
  total: number;
  limit: number;
  offset: number;
}
