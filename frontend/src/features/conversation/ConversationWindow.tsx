import { useEffect, useRef, useState, useCallback } from "react";
import { useRecoilValue } from "recoil";
import { currentConversationState } from "../../state/atoms";
import { conversationsApi, documentsApi } from "../../services/api";
import { socketService } from "../../services/socket";
import { Button, LoadingSpinner } from "../../components/ui";
import { useUpdates } from "../updates/UpdatesProvider";
import { Send, Upload, FileText, X, CheckCircle2, AlertCircle } from "lucide-react";
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
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [isUploading, setIsUploading] = useState(false);
  const [processingDocs, setProcessingDocs] = useState<Set<string>>(new Set());
  const [isDocumentsExpanded, setIsDocumentsExpanded] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageHandlerRef = useRef<((data: any) => void) | null>(null);
  const docProcessedHandlerRef = useRef<((data: any) => void) | null>(null);
  const { showToast } = useUpdates();

  // Deduplicate messages by ID
  const addMessage = useCallback((newMessage: Message) => {
    setMessages((prev) => {
      // Check if message already exists
      const exists = prev.some((m) => m.id === newMessage.id);
      if (exists) {
        return prev;
      }
      return [...prev, newMessage];
    });
  }, []);

  useEffect(() => {
    if (conversationId) {
      loadConversation();
      connectSocket();
    }

    return () => {
      if (conversationId) {
        socketService.leaveConversation(conversationId);
      }
      // Clean up socket listeners
      if (messageHandlerRef.current) {
        socketService.offMessage(messageHandlerRef.current);
      }
      if (docProcessedHandlerRef.current) {
        socketService.offDocumentProcessed(docProcessedHandlerRef.current);
      }
    };
  }, [conversationId]);

  useEffect(() => {
    if (conversation) {
      setMessages(conversation.messages || []);
      const docs = conversation.documents || [];
      // Remove duplicates by ID
      const uniqueDocs = Array.from(
        new Map(docs.map(doc => [doc.id, doc])).values()
      );
      console.log("📄 Loaded documents:", uniqueDocs.map(d => ({ 
        id: d.id, 
        filename: d.filename, 
        snippet: d.content_snippet?.substring(0, 50),
        isProcessed: d.content_snippet?.startsWith("Processed")
      })));
      setDocuments(uniqueDocs);
      
      // Mark documents as processing if they are still being processed
      const processing = new Set<string>();
      uniqueDocs.forEach((doc) => {
        // Document is processing if content_snippet is "Processing..." 
        // and it's not yet processed (doesn't start with "Processed")
        const isProcessing = doc.content_snippet === "Processing..." || 
            (doc.content_snippet && !doc.content_snippet.startsWith("Processed") && !doc.embedding);
        if (isProcessing) {
          processing.add(doc.id);
          console.log("⏳ Document still processing:", doc.id, doc.filename);
        } else {
          console.log("✅ Document ready:", doc.id, doc.filename, doc.content_snippet?.substring(0, 30));
        }
      });
      setProcessingDocs(processing);
    }
  }, [conversation]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Poll for document status updates if documents are processing
  useEffect(() => {
    if (processingDocs.size === 0 || !conversationId) return;

    const interval = setInterval(() => {
      console.log("🔄 Polling for document status updates...");
      loadConversation();
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [processingDocs.size, conversationId]);

  const loadConversation = async () => {
    if (!conversationId) return;

    try {
      setIsLoading(true);
      const data = await conversationsApi.get(conversationId);
      setMessages(data.messages || []);
      const docs = data.documents || [];
      // Remove duplicates by ID
      const uniqueDocs = Array.from(
        new Map(docs.map(doc => [doc.id, doc])).values()
      );
      console.log("📄 Loaded unique documents:", uniqueDocs.map(d => ({ 
        id: d.id, 
        filename: d.filename,
        isProcessed: d.content_snippet?.startsWith("Processed")
      })));
      setDocuments(uniqueDocs);
      
      // Mark documents as processing
      const processing = new Set<string>();
      uniqueDocs.forEach((doc) => {
        // Document is processing if content_snippet is "Processing..." 
        // and it's not yet processed (doesn't start with "Processed")
        if (doc.content_snippet === "Processing..." || 
            (doc.content_snippet && !doc.content_snippet.startsWith("Processed") && !doc.embedding)) {
          processing.add(doc.id);
        }
      });
      setProcessingDocs(processing);
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

    // Set up message handler
    const messageHandler = (data: Message) => {
      console.log("📨 Received message via Socket.IO:", data);
      // Only add if it's not a user message we already added optimistically
      // User messages from Socket.IO are duplicates, we get them from API response
      if (data.role !== "user") {
        addMessage(data);
      } else {
        console.log("⏭️ Skipping user message from Socket.IO (already added optimistically)");
      }
    };
    messageHandlerRef.current = messageHandler;
    socketService.onMessage(messageHandler);

    // Set up document processed handler
    const docProcessedHandler = (data: { doc_id?: string; status?: string; chunks?: number }) => {
      console.log("📢 Received doc_processed event:", data);
      if (data.doc_id) {
        console.log("✅ Removing from processing:", data.doc_id);
        setProcessingDocs((prev) => {
          const next = new Set(prev);
          next.delete(data.doc_id!);
          console.log("📊 Processing docs after removal:", Array.from(next));
          return next;
        });
        
        // Reload documents to get updated status
        setTimeout(() => {
          console.log("🔄 Reloading conversation after document processed");
          loadConversation();
        }, 1000); // Increased delay to ensure DB is updated
        
        showToast(
          `Document processed successfully! ${data.chunks || 0} chunks indexed. Ready to use.`,
          "success"
        );
      } else {
        console.warn("⚠️ doc_processed event missing doc_id:", data);
      }
    };
    docProcessedHandlerRef.current = docProcessedHandler;
    socketService.onDocumentProcessed(docProcessedHandler);
    
    // Also listen for any socket events for debugging
    const socket = socketService.getSocket();
    if (socket) {
      socket.onAny((event, ...args) => {
        console.log("🔌 Socket event received:", event, args);
      });
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = async () => {
    if (!conversationId || !input.trim() || isSending) return;

    const tempId = `temp-${Date.now()}`;
    const userMessage: Message = {
      id: tempId,
      conversation_id: conversationId,
      role: "user",
      content: input,
      created_at: new Date().toISOString(),
    };

    // Add optimistic message
    addMessage(userMessage);
    const messageContent = input;
    setInput("");
    setIsSending(true);

    try {
      const docIds = selectedDocIds.size > 0 ? Array.from(selectedDocIds) : undefined;
      console.log("📤 Sending message with doc_ids:", docIds, "Selected IDs:", Array.from(selectedDocIds));
      const response = await conversationsApi.sendMessage(conversationId, {
        content: messageContent,
        doc_ids: docIds,
      });
      
      // Replace temp message with real message from server
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempId);
        // Check if server message already exists (from Socket.IO)
        const exists = filtered.some((m) => m.id === response.id);
        if (!exists) {
          return [...filtered, response];
        }
        return filtered;
      });
    } catch (error) {
      console.error("Failed to send message:", error);
      // Remove temp message on error
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
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
          setProcessingDocs((prev) => new Set(prev).add(doc.id));
          showToast(`Uploaded ${file.name}. Processing...`, "info");
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
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      next.delete(docId);
      return next;
    });
  };

  const toggleDocumentSelection = (docId: string) => {
    console.log("🔄 Toggling document selection:", docId);
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
        console.log("❌ Deselected document:", docId);
      } else {
        next.add(docId);
        console.log("✅ Selected document:", docId, "Total selected:", next.size);
      }
      return next;
    });
  };

  const isDocumentReady = (doc: Document) => {
    // Document is ready if:
    // 1. content_snippet starts with "Processed" (backend updated it)
    // 2. OR it has an embedding (processed chunk)
    // 3. AND it's not "Processing..."
    if (doc.content_snippet === "Processing...") {
      return false;
    }
    if (doc.content_snippet && doc.content_snippet.startsWith("Processed")) {
      return true;
    }
    if (doc.embedding !== null && doc.embedding !== undefined) {
      return true;
    }
    return false;
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

  const readyDocuments = documents.filter(isDocumentReady);
  const hasSelectedDocs = selectedDocIds.size > 0;

  return (
    <div className="flex-1 flex flex-col bg-gray-50 dark:bg-gray-900 min-h-0 overflow-hidden">
      {/* Documents Bar - Fixed height, scrollable */}
      {documents.length > 0 && (
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Documents ({documents.length})
              </span>
              {hasSelectedDocs && (
                <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full">
                  {selectedDocIds.size} selected
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {hasSelectedDocs && (
                <button
                  onClick={() => setSelectedDocIds(new Set())}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Clear
                </button>
              )}
              <button
                onClick={() => setIsDocumentsExpanded(!isDocumentsExpanded)}
                className="text-xs text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
              >
                {isDocumentsExpanded ? "Hide" : "Show"}
              </button>
            </div>
          </div>
          {isDocumentsExpanded && (
            <div className="px-4 pb-3 max-h-40 overflow-y-auto overflow-x-hidden">
              <div className="flex items-center gap-2 flex-wrap">
                {documents.map((doc) => {
                  const isProcessing = processingDocs.has(doc.id);
                  const isReady = isDocumentReady(doc);
                  const isSelected = selectedDocIds.has(doc.id);

                  return (
                    <div
                      key={doc.id}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border shrink-0 cursor-pointer transition-all",
                        isSelected
                          ? "bg-blue-100 dark:bg-blue-900/30 border-blue-400 dark:border-blue-600"
                          : "bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700",
                        !isReady && "opacity-60"
                      )}
                      onClick={() => isReady && toggleDocumentSelection(doc.id)}
                      title={
                        isProcessing
                          ? "Processing document..."
                          : isReady
                          ? isSelected
                            ? "Click to deselect"
                            : "Click to select for grounding"
                          : "Document not ready"
                      }
                    >
                      {isProcessing ? (
                        <LoadingSpinner size="sm" />
                      ) : isReady ? (
                        isSelected ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-gray-600 dark:text-gray-400 shrink-0" />
                        )
                      ) : (
                        <AlertCircle className="w-3.5 h-3.5 text-yellow-600 dark:text-yellow-400 shrink-0" />
                      )}
                      <span
                        className={cn(
                          "text-xs truncate max-w-[150px]",
                          isSelected
                            ? "text-blue-900 dark:text-blue-100 font-medium"
                            : "text-gray-700 dark:text-gray-300"
                        )}
                      >
                        {doc.filename}
                      </span>
                      {isProcessing && (
                        <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                          ...
                        </span>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveDocument(doc.id);
                        }}
                        className="ml-0.5 p-0.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded shrink-0"
                        title="Remove document"
                      >
                        <X className="w-3 h-3 text-gray-500 dark:text-gray-400" />
                      </button>
                    </div>
                  );
                })}
              </div>
              {readyDocuments.length > 0 && !hasSelectedDocs && documents.length <= 10 && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                  💡 Tip: Click on documents to select them for grounding your questions
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Messages - Scrollable area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
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

      {/* Input Area - Fixed at bottom */}
      <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
        {hasSelectedDocs && (
          <div className="mb-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-xs text-blue-800 dark:text-blue-200">
              🎯 Your message will be grounded with {selectedDocIds.size} selected document{selectedDocIds.size > 1 ? "s" : ""}
            </p>
          </div>
        )}
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
              placeholder={
                hasSelectedDocs
                  ? `Ask about ${selectedDocIds.size} selected document${selectedDocIds.size > 1 ? "s" : ""}...`
                  : documents.length > 0
                  ? "Type your message or select documents to ground your question..."
                  : "Type your message..."
              }
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
