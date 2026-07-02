from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.services.chatbot import handle_user_message

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/send", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        convo, user_msg, bot_msg, reply = await handle_user_message(
            db,
            conversation_id=payload.conversation_id,
            external_conversation_id=payload.external_conversation_id,
            sender_id=payload.sender_id,
            content=payload.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # lỗi gọi OpenAI (rate limit, timeout, sai key...)
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    return ChatResponse(
        conversation_id=convo.id,
        user_message_id=user_msg.id,
        bot_message_id=bot_msg.id,
        reply=reply,
    )