"""
Chat Message Model and Repository

Handles persistence of chat messages between user and robot assistant.
Stores chat history for retrieval when WebSocket reconnects.
"""

from __future__ import annotations

from datetime import datetime
from bson import ObjectId
from typing import Optional, List, Dict, Any

from app.core.database import get_db


class ChatMessageModel:
    """Data model for chat messages"""
    
    def __init__(
        self,
        user_id: str | ObjectId,
        role: str,  # 'user' or 'assistant'
        content: str,
        timestamp: Optional[datetime] = None,
        message_id: Optional[str | ObjectId] = None,
    ):
        self.message_id = message_id or ObjectId()
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self.message_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChatMessageModel:
        return cls(
            user_id=data.get("user_id"),
            role=data.get("role"),
            content=data.get("content"),
            timestamp=data.get("timestamp"),
            message_id=data.get("_id"),
        )


class ChatRepository:
    """Repository for chat message persistence"""
    
    COLLECTION_NAME = "chat_messages"
    
    @staticmethod
    def _get_collection():
        db = get_db()
        return db[ChatRepository.COLLECTION_NAME]
    
    @classmethod
    async def save_message(cls, message: ChatMessageModel) -> str:
        """Save a chat message to database"""
        collection = cls._get_collection()
        
        result = await collection.insert_one(message.to_dict())
        return str(result.inserted_id)
    
    @classmethod
    async def get_user_history(
        cls,
        user_id: str | ObjectId,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get chat history for a user, newest first"""
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        collection = cls._get_collection()
        
        cursor = collection.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).skip(skip).limit(limit)
        
        messages = await cursor.to_list(length=limit)
        
        # Reverse to get chronological order (oldest first)
        return list(reversed(messages))
    
    @classmethod
    async def delete_user_history(
        cls,
        user_id: str | ObjectId,
    ) -> int:
        """Delete all chat history for a user (e.g., on account deletion)"""
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        collection = cls._get_collection()
        result = await collection.delete_many({"user_id": user_id})
        return result.deleted_count
    
    @classmethod
    async def cleanup_old_messages(cls, days: int = 90) -> int:
        """Delete messages older than specified days"""
        from datetime import timedelta
        
        collection = cls._get_collection()
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await collection.delete_many(
            {"timestamp": {"$lt": cutoff_date}}
        )
        return result.deleted_count
    
    @classmethod
    async def create_indexes(cls):
        """Create database indexes for optimal performance"""
        collection = cls._get_collection()
        
        # Index for quick user lookup with sorting
        await collection.create_index([("user_id", 1), ("timestamp", -1)])
        
        # Index for cleanup (delete old messages)
        await collection.create_index([("timestamp", 1)])
