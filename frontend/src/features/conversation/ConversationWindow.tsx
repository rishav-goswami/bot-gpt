import { useEffect, useRef, useState } from "react";
import { useRecoilValue } from "recoil";
import { currentConversationState } from "../../state/atoms";
import { conversationsApi, documentsApi } from "../../services/api";
import { socketService } from "../../services/socket";
import { Button, LoadingSpinner } from "../../components/ui";
import { useUpdates } from "../updates/UpdatesProvider";
import { Send, Upload, FileText, X } from "lucide-react";
import { cn } from "../../utils/cn";
import type { Message, Document } from "../../types";

interface ConversationWindowProps {
  conversationId: string | null;
}

export const ConversationWindow = ({
  conversationId,
}: ConversationWindowProps) => {
  const conversation = useRecoilValue(currentConversationState);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useUpdates();

  useEffect(() => {
    if (conversationId) {
      loadConversation();
      connectSocket();
    }

    return () => {
      if (conversationId) {
        socketService.leaveConversation(conversationId);
      }
    };
  }, [conversationId]);

  useEffect(() => {
    if (conversation) {
      setMessages(conversation.messages || []);
      setDocuments(conversation.documents || []);
    }
  }, [conversation]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadConversation = async () => {
    if (!conversationId) return;

    try {
      setIsLoading(true);
      const data = await conversationsApi.get(conversationId);
      setMessages(data.messages || []);
      setDocuments(data.documents || []);
    } catch (error) {
      console.error("Failed to load conversation:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const connectSocket = () => {
    if (!conversationId) return;

    socketService.connect();
    socketService.joinConversation(conversationId);

    socketService.onMessage((data) => {
      setMessages((prev) => [...prev, data]);
    });
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = async () => {
    if (!conversationId || !input.trim() || isSending) return;

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: conversationId,
      role: "user",
      content: input,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    try {
      await conversationsApi.sendMessage(conversationId, {
        content: userMessage.content,
      });
    } catch (error) {
      console.error("Failed to send message:", error);
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
      showToast("Failed to send message", "error");
    } finally {
      setIsSending(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || !conversationId) return;

    setIsUploading(true);

    try {
      for (const file of Array.from(files)) {
        if (file.type === "application/pdf") {
          const doc = await documentsApi.upload(conversationId, file);
          setDocuments((prev) => [...prev, doc]);
          showToast(`Uploaded ${file.name}`, "success");
        } else {
          showToast(`${file.name} is not a PDF file`, "warning");
        }
      }
    } catch (error) {
      console.error("Failed to upload document:", error);
      showToast("Failed to upload document", "error");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveDocument = async (docId: string) => {
    // TODO: Implement document deletion API
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  };

  if (!conversationId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            Select a conversation or start a new chat
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Documents Bar */}
      {documents.length > 0 && (
        <div className="px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 overflow-x-auto">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800"
            >
              <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span className="text-sm text-blue-900 dark:text-blue-100 truncate max-w-[200px]">
                {doc.filename}
              </span>
              <button
                onClick={() => handleRemoveDocument(doc.id)}
                className="ml-1 p-0.5 hover:bg-blue-200 dark:hover:bg-blue-800 rounded"
              >
                <X className="w-3 h-3 text-blue-600 dark:text-blue-400" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {isSending && (
          <div className="flex justify-start">
            <div className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-lg">
              <LoadingSpinner size="sm" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-end gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf"
            multiple
            className="hidden"
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            title="Upload PDF"
          >
            {isUploading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Upload className="w-5 h-5" />
            )}
          </Button>
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Type your message..."
              rows={1}
              className={cn(
                "w-full px-4 py-3 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg",
                "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                "focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none",
                "max-h-32 overflow-y-auto"
              )}
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSend}
            disabled={!input.trim() || isSending}
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </div>
  );
};

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[70%] rounded-lg px-4 py-2",
          isUser
            ? "bg-blue-600 text-white"
            : "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700"
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        <p className="text-xs mt-1 opacity-70">
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
};

