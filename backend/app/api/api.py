from fastapi import APIRouter
from app.api.v1.endpoints import chats

# from app.api.v1.endpoints import auth # (Future)
from app.api.v1.endpoints import documents

api_router = APIRouter()

api_router.include_router(chats.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
