
import { apiClient } from "./apiClient";

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  message_order: number;
  role: string;
  content: string | null;
  message_data: Record<string, unknown>;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[];
}

export interface ConversationListResponse {
  items: ConversationSummary[];
  total: number;
  limit: number;
  offset: number;
}

export function getConversations(
  limit = 20,
  offset = 0,
): Promise<ConversationListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  return apiClient.get(
    `/api/conversations?${params.toString()}`,
  );
}

export function getConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  return apiClient.get(
    `/api/conversations/${conversationId}`,
  );
}

export function renameConversation(
  conversationId: string,
  title: string,
): Promise<ConversationSummary> {
  return apiClient.patch(
    `/api/conversations/${conversationId}`,
    { title },
  );
}

export function deleteConversation(
  conversationId: string,
): Promise<void> {
  return apiClient.delete(
    `/api/conversations/${conversationId}`,
  );
}
