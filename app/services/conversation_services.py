from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional, List, Tuple

from app.models.conversation import Conversation
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate
)


# =========================
# GET BY UNIQUE KEY
# =========================
async def get_conversation(
    db: AsyncSession,
    external_conversation_id: Optional[str] = None,
    conversation_id: Optional[int] = None,
) -> Optional[Conversation]:
    try:
        query = select(Conversation)

        if conversation_id:
            query = query.where(Conversation.id == conversation_id)

        if external_conversation_id:
            query = query.where(
                Conversation.external_conversation_id == external_conversation_id
            )

        result = await db.execute(query)
        return result.scalars().first()

    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# UPSERT
# =========================
async def upsert_conversation(
    db: AsyncSession,
    data: ConversationCreate
) -> Conversation:
    try:
        convo = None

        if data.external_conversation_id:
            convo = await get_conversation(
                db,
                external_conversation_id=data.external_conversation_id,
            )

        # create
        if not convo:
            convo = Conversation(**data.model_dump())
            db.add(convo)
            await db.commit()
            await db.refresh(convo)
            return convo

        # update nhẹ nếu cần
        if data.status and data.status != convo.status:
            convo.status = data.status
            await db.commit()
            await db.refresh(convo)

        return convo

    except IntegrityError:
        await db.rollback()
        # race condition → retry
        return await get_conversation(
            db,
            external_conversation_id=data.external_conversation_id,
        )

    except SQLAlchemyError as e:
        await db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# UPDATE
# =========================
async def update_conversation(
    db: AsyncSession,
    conversation_id: int,
    data: ConversationUpdate
) -> Conversation:
    try:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        convo = result.scalars().first()

        if not convo:
            raise ValueError("Conversation not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(convo, field, value)

        await db.commit()
        await db.refresh(convo)
        return convo

    except ValueError:
        await db.rollback()
        raise

    except IntegrityError:
        await db.rollback()
        raise ValueError("Update conflict")

    except SQLAlchemyError as e:
        await db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# LIST
# =========================
async def list_conversations(
    db: AsyncSession,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[int, List[Conversation]]:
    try:
        base_query = select(Conversation)
        count_query = select(func.count()).select_from(Conversation)

        if status:
            base_query = base_query.where(Conversation.status == status)
            count_query = count_query.where(Conversation.status == status)

        total = (await db.execute(count_query)).scalar()

        query = base_query.order_by(Conversation.updated_at.desc())
        query = query.limit(limit).offset(offset)

        result = await db.execute(query)

        return total, result.scalars().all()

    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# DELETE
# =========================
async def delete_conversation(
    db: AsyncSession,
    conversation_id: int,
) -> bool:
    try:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        convo = result.scalars().first()

        if not convo:
            raise ValueError("Conversation not found")

        await db.delete(convo)
        await db.commit()
        return True

    except ValueError:
        await db.rollback()
        raise

    except SQLAlchemyError as e:
        await db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")