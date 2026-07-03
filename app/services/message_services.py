from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.schemas.message import MessageCreate, MessageUpdate

async def get_message(db: AsyncSession, message_id: int) -> Message | None:
    result = await db.execute(select(Message).where(Message.id == message_id))
    return result.scalar_one_or_none()


async def update_message(
    db: AsyncSession, message_id: int, data: MessageUpdate
) -> Message | None:
    msg = await get_message(db, message_id)
    if not msg:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(msg, field, value)

    await db.commit()
    await db.refresh(msg)
    return msg


async def delete_message(db: AsyncSession, message_id: int) -> bool:
    msg = await get_message(db, message_id)
    if not msg:
        return False
    await db.delete(msg)
    await db.commit()
    return True

async def get_message_by_external_id(
    db: AsyncSession, conversation_id: int, external_message_id: str
) -> Message | None:
    result = await db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.external_message_id == external_message_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_message(db: AsyncSession, data: MessageCreate) -> Message:
    """
    Nếu external_message_id đã tồn tại trong cùng conversation -> update content/status.
    Nếu chưa -> tạo mới. Nếu external_message_id là None -> luôn tạo mới.
    """
    existing = None
    if data.external_message_id:
        existing = await get_message_by_external_id(
            db, data.conversation_id, data.external_message_id
        )

    if existing:
        existing.content = data.content
        existing.status = data.status
        await db.commit()
        await db.refresh(existing)
        return existing

    msg = Message(
        conversation_id=data.conversation_id,
        external_message_id=data.external_message_id,
        sender_type=data.sender_type,
        sender_id=data.sender_id,
        message_type=data.message_type,
        content=data.content,
        status=data.status,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(
    db: AsyncSession, conversation_id: int, limit: int = 20, offset: int = 0
) -> tuple[int, list[Message]]:
    """
    Trả về (total, messages) — messages sắp xếp mới nhất trước (DESC).
    Caller cần tự đảo ngược nếu muốn thứ tự cũ -> mới (ví dụ khi build prompt cho LLM).
    """
    count_result = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = result.scalars().all()
    return total, items