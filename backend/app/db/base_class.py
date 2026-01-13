# File: app/db/base_class.py
from typing import Any
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    AsyncAttrs allows using awaitable attributes like .awaitable_attrs.
    """
    pass