import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.chatbot import ChatMessageRequest, ChatMessageResponse
from app.services.chatbot_services import handle_user_message
from app.services.message_services import list_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatMessageResponse)
async def chat(req: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
    if not req.conversation_id and not req.external_conversation_id:
        raise HTTPException(
            status_code=400,
            detail="Cần cung cấp conversation_id hoặc external_conversation_id",
        )

    try:
        convo, user_msg, bot_msg, reply_text = await handle_user_message(
            db,
            conversation_id=req.conversation_id,
            external_conversation_id=req.external_conversation_id,
            channel_account_id=req.channel_account_id,
            sender_id=req.sender_id,
            content=req.content,
            external_message_id=req.external_message_id,
        )

        _, history = await list_messages(db, conversation_id=convo.id, limit=100, offset=0)
        history = list(reversed(history))

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Lỗi xử lý chat message")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

    return ChatMessageResponse(
        conversation_id=convo.id,
        reply=reply_text,
        # messages=[
        #     {
        #         "sender_type": m.sender_type,
        #         "content": m.content,
        #         "created_at": m.created_at.isoformat(),
        #     }
        #     for m in history
        # ],
    )
#
# @router.post("/text-only", response_model=MessageRead, status_code=201)
# async def chat_text_only(req: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
#     """
#     Chỉ lưu tin nhắn text của user vào DB, không gọi bot sinh câu trả lời.
#     Dùng cho các trường hợp: log tin nhắn, webhook nhận tin không cần auto-reply, v.v.
#     """
#     if not req.conversation_id and not req.external_conversation_id:
#         raise HTTPException(
#             status_code=400,
#             detail="Cần cung cấp conversation_id hoặc external_conversation_id",
#         )
#
#     try:
#         # 1. Resolve conversation (lấy sẵn hoặc tạo mới nếu dùng external_conversation_id)
#         if req.conversation_id:
#             convo = await get_conversation(db, req.conversation_id)
#             if not convo:
#                 raise ValueError("Conversation not found")
#         else:
#             convo = await upsert_conversation(
#                 db,
#                 ConversationCreate(
#                     external_conversation_id=req.external_conversation_id
#                 ),
#             )
#
#         # 2. Lưu tin nhắn user, không gọi bot
#         user_msg = await upsert_message(
#             db,
#             MessageCreate(
#                 conversation_id=convo.id,
#                 external_message_id=req.external_message_id,
#                 sender_type="customer",
#                 sender_id=req.sender_id,
#                 message_type="text",
#                 content=req.content,
#             ),
#         )
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         logger.exception("Lỗi lưu tin nhắn text-only")
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
#
#     return user_msg
