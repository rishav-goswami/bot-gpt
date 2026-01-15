import { useEffect } from "react";
import { useRecoilValue, useSetRecoilState } from "recoil";
import { currentConversationState } from "../state/atoms";
import { conversationsApi } from "../services/api/conversations";

/**
 * Hook to preload conversation data when ID changes
 */
export const useConversationPreload = (conversationId: string | null) => {
  const currentConversation = useRecoilValue(currentConversationState);
  const setCurrentConversation = useSetRecoilState(currentConversationState);

  useEffect(() => {
    if (!conversationId) {
      setCurrentConversation(null);
      return;
    }

    // Only fetch if we don't have the conversation or it's a different ID
    if (
      !currentConversation ||
      currentConversation.id !== conversationId
    ) {
      const loadConversation = async () => {
        try {
          const conversation = await conversationsApi.get(conversationId);
          setCurrentConversation(conversation);
        } catch (error) {
          console.error("Failed to preload conversation:", error);
        }
      };

      loadConversation();
    }
  }, [conversationId, currentConversation, setCurrentConversation]);
};

