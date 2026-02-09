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
    # sources = Column(JSON, nullable=True)  # No longer used, metadata_info is source of truth

    @property
    def sources(self):
        """
        Dynamically construct sources list from metadata_info.
        """
        sources_list = []
        if not self.metadata_info:
            return sources_list

        meta = self.metadata_info
        rag_res = meta.get('rag_result')
        web_res = meta.get('web_result') or meta.get('web_resul')

        if rag_res:
            # Handle RAG
            chunks = []
            if isinstance(rag_res, dict) and 'chunkList' in rag_res:
                chunks = rag_res['chunkList']
            elif isinstance(rag_res, list):
                chunks = rag_res
            elif isinstance(rag_res, dict):
                chunks = [rag_res]
            
            for item in chunks:
                if isinstance(item, dict):
                    # Copy all fields to preserve rich content (images, score, content, etc.)
                    s_item = item.copy()
                    
                    # Ensure standard fields for frontend display
                    s_item["title"] = item.get('title') or item.get('documentName') or '知识库文档'
                    s_item["url"] = item.get('docUrl') or item.get('url') or '#'
                    s_item["type"] = "rag"
                    
                    sources_list.append(s_item)

        if web_res:
             # Handle Web
             items = []
             if isinstance(web_res, list):
                 items = web_res
             elif isinstance(web_res, dict):
                 items = [web_res]
             
             for item in items:
                 if isinstance(item, dict):
                     # Copy all fields to preserve rich content
                     s_item = item.copy()
                     
                     # Ensure standard fields for frontend display
                     s_item["title"] = item.get('title') or '网络搜索结果'
                     s_item["url"] = item.get('link') or item.get('url') or '#'
                     s_item["type"] = "web"
                     
                     sources_list.append(s_item)
        
        return sources_list # Store retrieval sources
    metadata_info = Column(JSON, nullable=True) # Rename from metadata to avoid conflict with SQLAlchemy
    created_at = Column(DateTime(timezone=True), server_default=func.now())
