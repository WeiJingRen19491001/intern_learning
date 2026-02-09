import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from app.db.session import get_db, AsyncSessionLocal
from app.schemas.chat import ChatRequest, ChatHistoryItem
from app.services.chat_service import ChatService
from app.models.chat_log import ChatLog
from loguru import logger
import json
import asyncio
import uuid

router = APIRouter()

@router.get("/history", response_model=List[ChatHistoryItem])
async def get_history(limit: int = 30):
    """
    Get the last N chat records globally.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChatLog).order_by(desc(ChatLog.created_at)).limit(limit)
        )
        logs = result.scalars().all()
        return logs

@router.delete("/history/{log_id}")
async def delete_chat_log(log_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ChatLog).where(ChatLog.id == log_id))
        chat_log = result.scalars().first()
        if not chat_log:
            raise HTTPException(status_code=404, detail="Chat log not found")
        
        await session.delete(chat_log)
        await session.commit()
        return {"message": "Deleted successfully"}

@router.post("/ask")
async def ask_question(request: ChatRequest):
    """
    Chat endpoint that returns a Server-Sent Events (SSE) stream.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Quesion cannot be empty")

    logger.info(f"Received question: {request.question}")
    
    # We generate UUID here to track it across stream and save
    # request_id = str(uuid.uuid4())

    async def event_generator():
        full_response_text = ""
        sources = []
        usage = None
        latency = None
        rag_result = None
        web_result = None
        
        # Track effective Request ID (fallback to UUID, prefer Aliyun ID)

        # final_request_id = request_id 自改

        # 1. Stream from Bailian
        async for data_str in ChatService.chat_stream_generator(request.question, request.session_id, request_id=None): #自改为 None
            # Capture data for DB
            try:
                data = json.loads(data_str)
                if "text" in data and data["text"]:
                     full_response_text += data["text"]
                if "sources" in data and data["sources"]:
                     sources = data["sources"]
                if "usage" in data and data["usage"]:
                     usage = data["usage"]
                if "latency" in data and data["latency"]:
                     latency = data["latency"]
                if "rag_result" in data and data["rag_result"]:
                     rag_result = data["rag_result"]
                if "web_result" in data and data["web_result"]:
                     web_result = data["web_result"]
                
                # Capture Aliyun Request ID if available
                if "request_id" in data and data["request_id"] and data["request_id"] != "init":
                     final_request_id = data["request_id"]
            except:
                pass
            
            yield f"data: {data_str}\n\n"
            await asyncio.sleep(0.02) # Throttling for UI
        
        yield "data: [DONE]\n\n"

        # 2. Save to DB after stream finishes
        # Check if we got any response
        if full_response_text or sources:
            logger.info(f"Saving chat log for {final_request_id}...")
            try:
                # Use a new session manually
                async with AsyncSessionLocal() as session:
                    chat_log = ChatLog(
                        request_id=final_request_id,
                        session_id=request.session_id,
                        user_query=request.question,
                        ai_response=full_response_text,
                        sources=sources,
                        metadata_info={
                            "usage": usage,
                            "latency": latency,
                            "rag_result": rag_result,
                            "web_result": web_result
                        }
                    )
                    session.add(chat_log)
                    await session.commit()
                    logger.info(f"Successfully saved chat log {final_request_id}")
            except Exception as e:
                logger.error(f"Failed to save chat log: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
