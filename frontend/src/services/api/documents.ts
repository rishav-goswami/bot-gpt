import { apiClient } from "./client";
import { API_ENDPOINTS } from "../../config";
import type { Document } from "../../types";

export const documentsApi = {
  /**
   * Upload a document to a conversation
   */
  upload: async (
    conversationId: string,
    file: File
  ): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("conversation_id", conversationId);

    const response = await apiClient.post<Document>(
      API_ENDPOINTS.documents,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  },

  /**
   * Get all documents for a conversation
   */
  list: async (conversationId: string): Promise<Document[]> => {
    const response = await apiClient.get<Document[]>(
      `${API_ENDPOINTS.documents}/${conversationId}`
    );
    return response.data;
  },
};

