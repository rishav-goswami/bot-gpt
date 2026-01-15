export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface Document {
  id: string;
  conversation_id: string | null;
  filename: string;
  file_path: string;
  content_snippet?: string;
  created_at: string;
  embedding?: number[] | null; // null means still processing
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages?: Message[];
  documents?: Document[];
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatCreate {
  first_message: string;
  doc_ids?: string[];
}

export interface MessageCreate {
  content: string;
  role?: "user" | "assistant" | "system";
  doc_ids?: string[];
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

