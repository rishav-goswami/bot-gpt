from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.core.database import AsyncSessionLocal
from app.db.models import User
from sqlalchemy import select


# Database Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Mock Auth Dependency for now
async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """
    Returns a demo user. In a real app, this would decode the JWT token.
    """
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(email="demo@botconsulting.io")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user
