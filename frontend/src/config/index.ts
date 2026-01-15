export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const API_V1_STR = "/api/v1";
export const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:8000";

export const API_ENDPOINTS = {
  conversations: `${API_V1_STR}/conversations`,
  documents: `${API_V1_STR}/documents`,
  health: "/health",
} as const;

