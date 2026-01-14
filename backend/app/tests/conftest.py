import pytest
import pytest_asyncio
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.db.models import User
from app.db.base import Base
from app.api.deps import get_current_user

# 1. Define Static User Data
TEST_USER_ID = uuid.UUID("17713e72-cba9-44cd-82eb-8c75b66d769b")
TEST_USER_EMAIL = "test_user@botgpt.com"


# 2. Global Event Loop (Fixes loop mismatch errors)
@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# 3. Database Setup (Create tables once per session)
@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine and set up tables."""
    engine = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
    )
    
    # Create tables and enable pgvector
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup: Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


# 4. Database Session
@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Create a database session for each test."""
    async_session = async_sessionmaker(
        bind=db_engine, 
        expire_on_commit=False,
        class_=AsyncSession
    )
    
    session = async_session()
    try:
        yield session
    finally:
        # Clean up: rollback any uncommitted changes and close
        try:
            await session.rollback()
        except Exception:
            pass
        try:
            await session.close()
        except Exception:
            pass


# 5. Override Database Dependency (includes user seeding)
@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session):
    """Override the get_db dependency to use test database and seed user."""
    # Seed user when database is used
    try:
        # Try to insert
        user = User(id=TEST_USER_ID, email=TEST_USER_EMAIL)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    except IntegrityError:
        # If user exists, rollback and ignore (it's fine)
        await db_session.rollback()
        # Try to get existing user
        from sqlalchemy import select
        result = await db_session.execute(select(User).where(User.id == TEST_USER_ID))
        user = result.scalars().first()
        if not user:
            # If still not found, try again
            user = User(id=TEST_USER_ID, email=TEST_USER_EMAIL)
            db_session.add(user)
            await db_session.commit()
    
    async def _get_db():
        yield db_session
    
    from app.api.deps import get_db
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


# 7. HTTP Client & Auth Override
@pytest_asyncio.fixture(scope="function")
async def client(override_get_db):
    """Create an async HTTP client for testing."""
    async def mock_get_current_user():
        return User(id=TEST_USER_ID, email=TEST_USER_EMAIL)

    app.dependency_overrides[get_current_user] = mock_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    # Cleanup
    app.dependency_overrides.pop(get_current_user, None)
