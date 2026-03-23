"""
Chat Router
Handles chat history endpoints and WebSocket connections

Endpoints:
- GET /api/bots/chat-history - Get user's chat history
- POST /api/bots/chat-message - Save a chat message
- POST /api/bots/chat-ai - Send message to AI trading assistant
- DELETE /api/bots/chat-history - Clear chat history
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.chat.models import ChatRepository, ChatMessageModel
from app.core.user_helpers import get_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["chat"])


@router.get("/chat-history")
async def get_chat_history(
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's chat history with the robot assistant
    
    Query Parameters:
    - limit: Number of messages to return (default: 50, max: 500)
    - skip: Number of messages to skip (for pagination)
    
    Returns:
    ```json
    {
        "messages": [
            {
                "id": "msg_1",
                "role": "user|assistant",
                "content": "Message text",
                "timestamp": "2026-02-12T10:30:00Z"
            }
        ],
        "total": 150,
        "limit": 50,
        "skip": 0
    }
    ```
    """
    try:
        user_id = get_user_id(current_user)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user context"
            )
        
        # Fetch messages from database
        messages = await ChatRepository.get_user_history(
            user_id=user_id,
            limit=limit,
            skip=skip
        )
        
        # Transform to response format
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "id": str(msg.get("_id", "")),
                "role": msg.get("role", "assistant"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", "").isoformat() if hasattr(msg.get("timestamp"), "isoformat") else str(msg.get("timestamp", "")),
            })
        
        logger.info(f"[✓] Retrieved {len(messages)} chat messages for user {user_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "messages": formatted_messages,
                "total": len(formatted_messages),
                "limit": limit,
                "skip": skip,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[✗] Error retrieving chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat history"
        )


@router.post("/chat-message")
async def save_chat_message(
    message_data: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Save a chat message sent by user (called before sending to assistant)
    
    Should be called after successful send, not before.
    This ensures only actually sent messages are stored.
    
    Request Body:
    ```json
    {
        "role": "user|assistant",
        "content": "Message text"
    }
    ```
    """
    try:
        user_id = get_user_id(current_user)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user context"
            )
        
        role = message_data.get("role")
        content = message_data.get("content")
        
        if not role or not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'role' or 'content' field"
            )
        
        if role not in ("user", "assistant"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be 'user' or 'assistant'"
            )
        
        # Create and save message
        message = ChatMessageModel(
            user_id=user_id,
            role=role,
            content=content
        )
        
        message_id = await ChatRepository.save_message(message)
        
        logger.info(f"[✓] Saved {role} message for user {user_id}: {message_id}")
        
        return JSONResponse(
            status_code=201,
            content={
                "id": message_id,
                "role": role,
                "content": content,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[✗] Error saving chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message"
        )


@router.delete("/chat-history")
async def clear_chat_history(
    current_user: dict = Depends(get_current_user),
):
    """
    Clear all chat history for the current user
    
    ⚠️ WARNING: This is permanent and cannot be undone
    """
    try:
        user_id = get_user_id(current_user)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user context"
            )
        
        deleted_count = await ChatRepository.delete_user_history(user_id)
        
        logger.warning(f"[!] Cleared {deleted_count} chat messages for user {user_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "deleted": deleted_count,
                "message": f"Cleared {deleted_count} messages"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[✗] Error clearing chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear chat history"
        )


# ---------------------------------------------------------------------------
# AI-powered trading assistant
# ---------------------------------------------------------------------------

ASSISTANT_SYSTEM_PROMPT = (
    "You are CryptoBot, the AI trading assistant for Crypto Trade Hub. "
    "You help users understand crypto markets, trading strategies (scalping, grid, DCA, MACD crossover), "
    "risk management, technical indicators (RSI, MACD, Bollinger Bands), and how to configure their trading bots. "
    "Be concise, practical, and always remind users that trading involves risk. "
    "Answer in the same language the user writes in. "
    "Do NOT provide specific financial advice or guarantee profits."
)


@router.post("/chat-ai")
async def chat_with_ai(
    message_data: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Send a message to the AI trading assistant and get a response.

    Body: {"content": "your question here"}

    Returns the assistant's reply and saves both messages to history.
    """
    try:
        user_id = get_user_id(current_user)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user context",
            )

        content = (message_data.get("content") or "").strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'content' field",
            )

        # Save user message
        user_msg = ChatMessageModel(user_id=user_id, role="user", content=content)
        await ChatRepository.save_message(user_msg)

        # Build conversation context from recent history
        history = await ChatRepository.get_user_history(user_id, limit=10)
        messages = [{"role": "system", "content": ASSISTANT_SYSTEM_PROMPT}]
        for msg in history:
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg.get("content", "")})

        # Call Groq LLM
        from app.core.config import settings

        if not settings.groq_api_key:
            assistant_text = (
                "AI assistant is not configured yet. Please set the GROQ_API_KEY "
                "environment variable to enable AI responses."
            )
        else:
            from groq import Groq

            client = Groq(api_key=settings.groq_api_key)
            completion = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            assistant_text = completion.choices[0].message.content

        # Save assistant response
        assistant_msg = ChatMessageModel(
            user_id=user_id, role="assistant", content=assistant_text
        )
        msg_id = await ChatRepository.save_message(assistant_msg)

        logger.info(f"[✓] AI chat response for user {user_id}")

        return JSONResponse(
            status_code=200,
            content={
                "id": msg_id,
                "role": "assistant",
                "content": assistant_text,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[✗] Error in AI chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get AI response",
        )
