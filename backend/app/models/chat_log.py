from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True) # Optional session ID for history
    request_id = Column(String, index=True, unique=True, nullable=False) # Helper for tracking
    user_query = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=True) # Stored after completion
    sources = Column(JSON, nullable=True) # Store retrieval sources
    metadata_info = Column(JSON, nullable=True) # Rename from metadata to avoid conflict with SQLAlchemy
    created_at = Column(DateTime(timezone=True), server_default=func.now())
