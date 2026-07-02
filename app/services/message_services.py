
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional, List, Tuple

from app.models.message import Message
from app.schemas.message import (
    MessageCreate,
    MessageUpdate
)


# =========================
# GET BY UNIQUE KEY
# =========================
async def get_message(
    db: AsyncSession,
    conversation_id: int,
    external_message_id: Optional[str] = None,
    message_id: Optional[int] = None,
) -> Optional[Message]:
    try:
        query = select(Message).where(
            Message.conversation_id == conversation_id
        )

        if message_id:
            query = query.where(Message.id == message_id)

        if external_message_id:
            query = query.where(
                Message.external_message_id == external_message_id
            )

        result = await db.execute(query)
        return result.scalars().first()

    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# UPSERT
# =========================
async def upsert_message(
    db: AsyncSession,
    data: MessageCreate
) -> Message:
    try:
        msg = None

        if data.external_message_id:
            msg = await get_message(
                db,
                conversation_id=data.conversation_id,
                external_message_id=data.external_message_id,
            )

        # create
        if not msg:
            msg = Message(**data.model_dump())
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            return msg

        # update nhẹ nếu cần
        updated = False

        if data.status and data.status != msg.status:
            msg.status = data.status
            updated = True

        if data.content and data.content != msg.content:
            msg.content = data.content
            updated = True

        if updated:
            await db.commit()
            await db.refresh(msg)

        return msg

    except IntegrityError:
        await db.rollback()
        # race condition → retry
        return await get_message(
            db,
            conversation_id=data.conversation_id,
            external_message_id=data.external_message_id,
        )

    except SQLAlchemyError as e:
        await db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# UPDATE
# =========================
async def update_message(
    db: AsyncSession,
    message_id: int,
    conversation_id: int,
    data: MessageUpdate
) -> Message:
    try:
        result = await db.execute(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id
            )
        )
        msg = result.scalars().first()

        if not msg:
            raise ValueError("Message not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(msg, field, value)

        await db.commit()
        await db.refresh(msg)
        return msg

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
async def list_messages(
    db: AsyncSession,
    conversation_id: int,
    sender_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[int, List[Message]]:
    try:
        base_query = select(Message).where(
            Message.conversation_id == conversation_id
        )

        if sender_type:
            base_query = base_query.where(
                Message.sender_type == sender_type
            )

        count_query = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        )

        if sender_type:
            count_query = count_query.where(
                Message.sender_type == sender_type
            )

        total = (await db.execute(count_query)).scalar()

        query = base_query.order_by(Message.created_at.asc())
        query = query.limit(limit).offset(offset)

        result = await db.execute(query)

        return total, result.scalars().all()

    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error: {str(e)}")


# =========================
# DELETE
# =========================
async def delete_message(
    db: AsyncSession,
    message_id: int,
    conversation_id: int,
) -> bool:
    try:
        result = await db.execute(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id
            )
        )
        msg = result.scalars().first()

        if not msg:
            raise ValueError("Message not found")

        await db.delete(msg)
        await db.commit()
        return True

    except ValueError:
        await db.rollback()
        raise

    except SQLAlchemyError as e:
        await db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")