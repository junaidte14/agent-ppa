
import { apiClient } from "./apiClient";

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  conversation_id: string;
  reply: string;
}

export function sendChatMessage(
  request: ChatRequest,
): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>("/api/chat", request);
}
