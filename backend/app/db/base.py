from app.db.base_class import Base

#  all models here so Alembic can detect them
from app.db.models import User, Conversation, Message, Document
