import { useEffect } from "react";
import { useRecoilState, useRecoilValue, useSetRecoilState } from "recoil";
import { useNavigate } from "react-router-dom";
import {
  authState,
  currentConversationState,
  selectedConversationIdState,
} from "../../state/atoms";
import { conversationsApi } from "../../services/api/conversations";
import { useConversationPreload } from "../../hooks/useConversationPreload";
import { Sidebar } from "./Sidebar";
import { ConversationWindow } from "../conversation/ConversationWindow";
import { Button } from "../../components/ui";
import { useUpdates } from "../updates/UpdatesProvider";
import { LogOut, User, Settings } from "lucide-react";

export const DashboardPage = () => {
  const navigate = useNavigate();
  const auth = useRecoilValue(authState);
  const setAuth = useSetRecoilState(authState);
  const [selectedId, setSelectedId] = useRecoilState(selectedConversationIdState);
  const setCurrentConversation = useSetRecoilState(currentConversationState);
  const { showToast } = useUpdates();

  // Preload conversation when selected
  useConversationPreload(selectedId);

  useEffect(() => {
    if (!auth.isAuthenticated) {
      navigate("/login");
    }
  }, [auth.isAuthenticated, navigate]);

  const handleNewChat = async () => {
    try {
      const conversation = await conversationsApi.create({
        first_message: "Hello!",
      });
      setSelectedId(conversation.id);
      setCurrentConversation(conversation);
      showToast("New conversation created", "success");
    } catch (error) {
      console.error("Failed to create conversation:", error);
      showToast("Failed to create conversation", "error");
    }
  };

  const handleSelectConversation = async (id: string) => {
    if (!id) {
      setSelectedId(null);
      setCurrentConversation(null);
      return;
    }

    setSelectedId(id);
    try {
      const conversation = await conversationsApi.get(id);
      setCurrentConversation(conversation);
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  };

  const handleLogout = async () => {
    const { mockAuthService } = await import("../../services/auth/mockAuth");
    await mockAuthService.logout();
    setAuth({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
    navigate("/login");
  };

  if (!auth.isAuthenticated) {
    return null;
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Top Bar */}
      <div className="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          BotGPT
        </h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <User className="w-4 h-4" />
            <span>{auth.user?.email}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/profile")}
          >
            <Settings className="w-4 h-4 mr-2" />
            Profile
          </Button>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
        />
        <ConversationWindow conversationId={selectedId} />
      </div>
    </div>
  );
};

