import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text


from app.core.config import settings
from app.core.database import engine, Base
# from app.api.v1.api import api_router # TODO: will add this when I implement more routes
from app.middlewares.logging import RequestLoggingMiddleware
from app.services.socketio_manager import sio


# --- 1. Lifespan Manager (Startup & Shutdown) ---
# This replaces the old 'on_startup' list. It's cleaner for Async DBs.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create Tables (if not using Alembic for migrations)
    # In production, you typically use Alembic, but for this assessment, this ensures tables exist.
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Uncomment to reset DB on restart
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Database tables created (if they didn't exist).")
    print("🚀 System is ready to accept connections.")

    yield  # App runs here

    # Shutdown: Close DB connections (Async engine handles this mostly, but good practice)
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
# app.include_router(api_router, prefix=settings.API_V1_STR)

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
