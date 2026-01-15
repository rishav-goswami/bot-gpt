import { apiClient } from "./client";
import { API_ENDPOINTS } from "../../config";
import type {
  Conversation,
  ConversationSummary,
  ChatCreate,
  Message,
  MessageCreate,
} from "../../types";

export const conversationsApi = {
  /**
   * Create a new conversation
   */
  create: async (data: ChatCreate): Promise<Conversation> => {
    const response = await apiClient.post<Conversation>(
      API_ENDPOINTS.conversations,
      data
    );
    return response.data;
  },

  /**
   * Get all conversations for the current user
   */
  list: async (skip = 0, limit = 20): Promise<ConversationSummary[]> => {
    const response = await apiClient.get<ConversationSummary[]>(
      API_ENDPOINTS.conversations,
      { params: { skip, limit } }
    );
    return response.data;
  },

  /**
   * Get a specific conversation by ID
   */
  get: async (chatId: string): Promise<Conversation> => {
    const response = await apiClient.get<Conversation>(
      `${API_ENDPOINTS.conversations}/${chatId}`
    );
    return response.data;
  },

  /**
   * Send a message to a conversation
   */
  sendMessage: async (
    chatId: string,
    message: MessageCreate
  ): Promise<Message> => {
    const response = await apiClient.post<Message>(
      `${API_ENDPOINTS.conversations}/${chatId}/messages`,
      message
    );
    return response.data;
  },

  /**
   * Delete a conversation
   */
  delete: async (chatId: string): Promise<void> => {
    await apiClient.delete(`${API_ENDPOINTS.conversations}/${chatId}`);
  },
};

