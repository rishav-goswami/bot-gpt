import pytest
import pytest_asyncio
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import IntegrityError
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.db.models import User
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


# 3. Database Engine & Session
@pytest_asyncio.fixture(scope="function")
async def db_session():
    # Create engine per test to ensure isolation
    engine = create_async_engine(settings.ASYNC_DATABASE_URL)
    async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


# 4. Seed User (Robust Logic)
@pytest_asyncio.fixture(scope="function", autouse=True)
async def seed_user(db_session):
    """
    Ensures the test user exists. Handles 'Already Exists' errors gracefully.
    """
    try:
        # Try to insert
        user = User(id=TEST_USER_ID, email=TEST_USER_EMAIL)
        db_session.add(user)
        await db_session.commit()
    except IntegrityError:
        # If user exists, rollback and ignore (it's fine)
        await db_session.rollback()


# 5. HTTP Client & Auth Override
@pytest_asyncio.fixture(scope="function")
async def client():
    async def mock_get_current_user():
        return User(id=TEST_USER_ID, email=TEST_USER_EMAIL)

    app.dependency_overrides[get_current_user] = mock_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides = {}
