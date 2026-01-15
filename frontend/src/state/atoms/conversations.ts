import { atom } from "recoil";
import type { Conversation, ConversationSummary } from "../../types";

export const conversationsState = atom<ConversationSummary[]>({
  key: "conversationsState",
  default: [],
});

export const currentConversationState = atom<Conversation | null>({
  key: "currentConversationState",
  default: null,
});

export const selectedConversationIdState = atom<string | null>({
  key: "selectedConversationIdState",
  default: null,
});

