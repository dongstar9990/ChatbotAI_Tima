from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationCreate, ConversationUpdate


async def get_conversation(db: AsyncSession, conversation_id: int) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    return result.scalar_one_or_none()


async def get_conversation_by_external_id(
    db: AsyncSession, external_conversation_id: str
) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.external_conversation_id == external_conversation_id
        )
    )
    return result.scalar_one_or_none()


async def upsert_conversation(
    db: AsyncSession, data: ConversationCreate
) -> Conversation:
    """
    Nếu external_conversation_id đã tồn tại -> trả về conversation cũ.
    Nếu chưa -> tạo mới.
    """
    existing = await get_conversation_by_external_id(
        db, data.external_conversation_id
    )
    if existing:
        return existing

    convo = Conversation(
        external_conversation_id=data.external_conversation_id,
        channel_account_id=data.channel_account_id,
        status=data.status,
    )
    db.add(convo)
    await db.commit()
    await db.refresh(convo)
    return convo


async def update_conversation(
    db: AsyncSession, conversation_id: int, data: ConversationUpdate
) -> Conversation | None:
    convo = await get_conversation(db, conversation_id)
    if not convo:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(convo, field, value)

    await db.commit()
    await db.refresh(convo)
    return convo


async def list_conversations(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    channel_account_id: int | None = None,
) -> tuple[int, list[Conversation]]:
    filters = []
    if channel_account_id is not None:
        filters.append(Conversation.channel_account_id == channel_account_id)

    count_result = await db.execute(
        select(func.count()).select_from(Conversation).where(*filters)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Conversation)
        .where(*filters)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = result.scalars().all()
    return total, items


async def delete_conversation(db: AsyncSession, conversation_id: int) -> bool:
    convo = await get_conversation(db, conversation_id)
    if not convo:
        return False
    await db.delete(convo)
    await db.commit()
    return True