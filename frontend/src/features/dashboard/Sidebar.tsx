import { useEffect, useState } from "react";
import { useRecoilState, useRecoilValue } from "recoil";
import {
  conversationsState,
  selectedConversationIdState,
} from "../../state/atoms";
import { conversationsApi } from "../../services/api/conversations";
import { Button } from "../../components/ui";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useUpdates } from "../updates/UpdatesProvider";
import { Plus, MessageSquare, Trash2 } from "lucide-react";
import { cn } from "../../utils/cn";
import type { ConversationSummary } from "../../types";

interface SidebarProps {
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
}

export const Sidebar = ({ onNewChat, onSelectConversation }: SidebarProps) => {
  const [conversations, setConversations] = useRecoilState(conversationsState);
  const selectedId = useRecoilValue(selectedConversationIdState);
  const [isLoading, setIsLoading] = useState(true);
  const { showToast } = useUpdates();

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      setIsLoading(true);
      const data = await conversationsApi.list();
      setConversations(data);
    } catch (error) {
      console.error("Failed to load conversations:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this conversation?")) {
      try {
        await conversationsApi.delete(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (selectedId === id) {
          onSelectConversation("");
        }
        showToast("Conversation deleted", "success");
      } catch (error) {
        console.error("Failed to delete conversation:", error);
        showToast("Failed to delete conversation", "error");
      }
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="w-64 h-full bg-gray-900 dark:bg-gray-950 border-r border-gray-800 dark:border-gray-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <Button
          variant="primary"
          className="w-full"
          onClick={onNewChat}
          size="sm"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Chat
        </Button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <LoadingSpinner />
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No conversations yet</p>
            <p className="text-sm mt-2">Start a new chat to begin</p>
          </div>
        ) : (
          <div className="p-2">
            {conversations.map((conversation) => (
              <ConversationItem
                key={conversation.id}
                conversation={conversation}
                isSelected={selectedId === conversation.id}
                onSelect={() => onSelectConversation(conversation.id)}
                onDelete={(e) => handleDelete(e, conversation.id)}
                formatDate={formatDate}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

interface ConversationItemProps {
  conversation: ConversationSummary;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
  formatDate: (date: string) => string;
}

const ConversationItem = ({
  conversation,
  isSelected,
  onSelect,
  onDelete,
  formatDate,
}: ConversationItemProps) => {
  return (
    <div
      className={cn(
        "group relative p-3 mb-1 rounded-lg cursor-pointer transition-colors",
        isSelected
          ? "bg-gray-800 dark:bg-gray-800"
          : "hover:bg-gray-800/50 dark:hover:bg-gray-800/50"
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">
            {conversation.title || "New Conversation"}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {formatDate(conversation.updated_at)}
          </p>
        </div>
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-700 rounded transition-opacity"
          aria-label="Delete conversation"
        >
          <Trash2 className="w-4 h-4 text-gray-400 hover:text-red-400" />
        </button>
      </div>
    </div>
  );
};

