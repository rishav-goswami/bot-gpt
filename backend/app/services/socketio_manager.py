import socketio
from typing import Any
from app.core.config import settings


class SocketManager:
    def __init__(self):
        # Redis Manager allows this to scale across multiple workers/containers
        mgr = socketio.AsyncRedisManager(settings.REDIS_URL)

        # Async Server
        self.server = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",  # Allow React dev server
            client_manager=mgr,
        )
        self.app = socketio.ASGIApp(self.server)

        # Register Event Handlers
        self.server.on("connect", self.connect)
        self.server.on("disconnect", self.disconnect)
        self.server.on("join_conversation", self.join_conversation)
        self.server.on("send_message", self.handle_message)

    async def connect(self, sid: str, environ: dict):
        # In prod, check token in environ['QUERY_STRING'] or headers
        print(f"Socket Connected: {sid}")
        await self.server.emit("connection_ack", {"status": "connected"}, room=sid)

    async def disconnect(self, sid: str):
        print(f"Socket Disconnected: {sid}")

    async def join_conversation(self, sid: str, data: dict):
        """
        Frontend sends: {'conversation_id': 'uuid-string'}
        """
        room = data.get("conversation_id")
        if room:
            self.server.enter_room(sid, room)
            await self.server.emit("room_joined", {"room": room}, room=sid)
            print(f"SID {sid} joined room {room}")

    async def handle_message(self, sid: str, data: dict):
        """
        Handle incoming real-time messages.
        1. Save to DB (via a service call)
        2. Emit to others in room
        3. Trigger LLM
        """
        room = data.get("conversation_id")
        content = data.get("content")

        # Echo back immediately to confirm receipt
        await self.server.emit(
            "new_message", {"role": "user", "content": content}, room=room, skip_sid=sid
        )

        # TODO: Trigger Celery task or Background Task for LLM response
        # await self.emit_llm_response(room, content)

    async def emit_to_room(self, room: str, event: str, data: Any):
        await self.server.emit(event, data, room=room)


# Create Global Instance
sio = SocketManager()
