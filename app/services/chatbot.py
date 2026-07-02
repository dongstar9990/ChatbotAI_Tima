from typing import List
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models.message import Message
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageCreate
from app.services.conversation_services import get_conversation, upsert_conversation
from app.services.message_services import list_messages, upsert_message

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Bạn là trợ lý chăm sóc khách hàng thân thiện, trả lời ngắn gọn, rõ ràng, "
    "lịch sự bằng tiếng Việt."
)


def _build_history(messages: List[Message]) -> List[dict]:
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages:
        role = "user" if m.sender_type == "customer" else "assistant"
        history.append({"role": role, "content": m.content})
    return history


async def handle_user_message(
    db: AsyncSession,
    conversation_id: int | None,
    external_conversation_id: str | None,
    sender_id: int,
    content: str,
):
    # 1. Lấy hoặc tạo conversation
    if conversation_id:
        convo = await get_conversation(db, conversation_id=conversation_id)
        if not convo:
            raise ValueError(f"Conversation {conversation_id} not found")
    else:
        convo = await upsert_conversation(
            db,
            ConversationCreate(
                external_conversation_id=external_conversation_id,
                status=1,
            ),
        )

    # 2. Lưu tin nhắn của user
    user_msg = await upsert_message(
        db,
        MessageCreate(
            conversation_id=convo.id,
            sender_type="customer",
            sender_id=sender_id,
            message_type="text",
            content=content,
            status="sent",
        ),
    )

    # 3. Lấy lịch sử hội thoại (20 tin gần nhất)
    _, history_messages = await list_messages(
        db, conversation_id=convo.id, limit=20, offset=0
    )

    # 4. Gọi OpenAI
    completion = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=_build_history(history_messages),
        temperature=0.7,
    )
    reply_text = completion.choices[0].message.content

    # 5. Lưu tin nhắn trả lời của bot
    bot_msg = await upsert_message(
        db,
        MessageCreate(
            conversation_id=convo.id,
            sender_type="bot",
            sender_id=0,
            message_type="text",
            content=reply_text,
            status="sent",
        ),
    )

    return convo, user_msg, bot_msg, reply_text