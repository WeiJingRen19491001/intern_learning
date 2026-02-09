from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[Any]] = []
    request_id: Optional[str] = None

class ChatHistoryItem(BaseModel):
    id: int
    session_id: Optional[str] = None
    request_id: str
    user_query: str
    ai_response: Optional[str] = None
    sources: Optional[List[Any]] = None
    metadata_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

