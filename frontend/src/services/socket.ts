import { io, type Socket } from "socket.io-client";
import { SOCKET_URL } from "../config";

class SocketService {
  private socket: Socket | null = null;

  connect(): Socket {
    if (this.socket?.connected) {
      return this.socket;
    }

    this.socket = io(SOCKET_URL, {
      path: "/socket.io/",
      transports: ["websocket"],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
    });

    this.socket.on("connect", () => {
      console.log("Socket connected:", this.socket?.id);
    });

    this.socket.on("disconnect", () => {
      console.log("Socket disconnected");
    });

    this.socket.on("connection_ack", (data) => {
      console.log("Connection acknowledged:", data);
    });

    return this.socket;
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  joinConversation(conversationId: string): void {
    if (this.socket) {
      this.socket.emit("join_conversation", { conversation_id: conversationId });
    }
  }

  leaveConversation(conversationId: string): void {
    if (this.socket) {
      this.socket.emit("leave_conversation", { conversation_id: conversationId });
    }
  }

  onMessage(callback: (data: any) => void): void {
    if (this.socket) {
      this.socket.on("new_message", callback);
    }
  }

  offMessage(callback: (data: any) => void): void {
    if (this.socket) {
      this.socket.off("new_message", callback);
    }
  }

  onDocumentProcessed(callback: (data: any) => void): void {
    if (this.socket) {
      console.log("🎧 Registering doc_processed listener");
      this.socket.on("doc_processed", (data) => {
        console.log("📨 Raw doc_processed event received:", data);
        callback(data);
      });
    } else {
      console.warn("⚠️ Cannot register doc_processed listener: socket not connected");
    }
  }

  offDocumentProcessed(callback: (data: any) => void): void {
    if (this.socket) {
      this.socket.off("doc_processed", callback);
    }
  }

  getSocket(): Socket | null {
    return this.socket;
  }
}

export const socketService = new SocketService();

