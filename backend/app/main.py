import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text


from app.core.config import settings
from app.core.database import engine
from app.db.base import Base
from app.api.api import api_router
from app.middlewares.logging import RequestLoggingMiddleware
from app.services.socketio_manager import sio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Logic
    async with engine.begin() as conn:
        # 1. Enable pgvector extension (Crucial Fix)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # 2. Create Tables
        # await conn.run_sync(Base.metadata.drop_all) #  if needed to reset schema
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created & pgvector enabled.")
    print("🚀 System is ready to accept connections.")
    
    yield # App runs here
    
    # Shutdown Logic
    await engine.dispose()
    print("🛑 Database connection closed.")


# --- 2. FastAPI App Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,  # Inject the lifespan manager
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- 3. Middlewares ---

# A. Structured Logging (The one we wrote earlier)
# Captures Request ID, Duration, and Status Codes in JSON format
app.add_middleware(RequestLoggingMiddleware)

# B. CORS Middleware
# Crucial for your React frontend to communicate with this Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # Loaded from .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Routers ---
app.include_router(api_router, prefix=settings.API_V1_STR)

app.mount("/socket.io", sio.app) # Mount Socket.IO ASGI app

@app.get("/")
async def read_root():
    """Simple root endpoint to verify API is reachable."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health/live")
async def health_live():
    """Liveness probe (k8s style) - checks if the process is running."""
    return {"status": "ok", "service": "bot-gpt-backend"}


@app.get("/health")
async def health_check():
    """
    Full Health Check:
    1. connectivity to API
    2. connectivity to Database (Async Check)
    """
    start_time = time.time()
    db_status = "disconnected"
    error_msg = None

    try:
        # Perform a lightweight async SQL query to check DB connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        error_msg = str(e)
        db_status = "error"

    duration = round((time.time() - start_time) * 1000, 2)

    status_code = 200 if db_status == "connected" else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_status == "connected" else "unhealthy",
            "service": "bot-gpt-backend",
            "database": db_status,
            "latency_ms": duration,
            "error": error_msg,
        },
    )
