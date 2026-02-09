import uuid
from app.services.bailian_service import BailianService
from loguru import logger

class ChatService:
    @staticmethod
    async def chat_stream_generator(question: str, session_id: str, request_id: str|None = None):
        """
        Just yields chunks from Bailian. 
        DB saving is now handled by the caller (Router) to separate concerns.
        """
        # logger.info(f"Starting chat stream for {request_id}") 自改
        
        async for chunk_str in BailianService.stream_chat(question, session_id):
            yield chunk_str
