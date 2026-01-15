import asyncio
import socketio
from celery import shared_task
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)
from app.core.config import settings
from app.services.rag_service import rag_service


# Helper to send notifications from a Worker
async def notify_frontend(chat_id: str, data: dict):
    """
    Creates a temporary, write-only connection to Redis to emit the event.
    This is safe to run inside the Worker's unique event loop.
    """
    try:
        print(f"📡 Attempting to notify frontend for conversation {chat_id} with data: {data}")
        # Connect to the SAME Redis that the API uses
        redis_url = settings.REDIS_URL_RESOLVED
        if not redis_url:
            print("⚠️ REDIS_URL not set, cannot send notification")
            return
        
        print(f"🔗 Using Redis URL: {redis_url}")
        mgr = socketio.AsyncRedisManager(redis_url, write_only=True)
        tmp_server = socketio.AsyncServer(
            async_mode="asgi",
            client_manager=mgr,
            cors_allowed_origins="*"
        )

        # Emit the event to the room (conversation_id)
        print(f"📤 Emitting doc_processed to room: {chat_id}")
        await tmp_server.emit("doc_processed", data, room=str(chat_id))
        print(f"✅ Successfully emitted doc_processed event to room {chat_id}")

        # Clean up connection
        # await mgr.close()
    except Exception as e:
        print(f"⚠️ Notification Failed: {e}")
        import traceback
        traceback.print_exc()


async def run_ingest(doc_id, file_path, conversation_id):
    # 1. Create a FRESH Engine & Session for this specific loop
    # We cannot use the global 'engine' from core.database because it belongs to the wrong loop.
    local_engine = create_async_engine(settings.ASYNC_DATABASE_URL)
    LocalSession = async_sessionmaker(bind=local_engine, expire_on_commit=False)

    try:
        async with LocalSession() as session:
            # 2. Pass this fresh session to the service
            stats = await rag_service.process_document(
                doc_id, file_path, conversation_id, db=session
            )

            # 3. Send Notification with doc_id
            stats["doc_id"] = str(doc_id)
            print(f"📢 Emitting doc_processed event for doc {doc_id} in conversation {conversation_id}")
            await notify_frontend(str(conversation_id), stats)
            print(f"✅ Notification sent: {stats}")

    finally:
        # 4. Cleanup the engine
        await local_engine.dispose()


@shared_task(name="ingest_pdf")
def ingest_pdf_task(doc_id_str, file_path, conversation_id_str):
    """
    Wrapper to run async code in sync Celery worker.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_ingest(doc_id_str, file_path, conversation_id_str))
    finally:
        loop.close()
