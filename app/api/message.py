from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.db import get_db
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageRead,
    MessageListResponse,
)
from app.services.message_services import (
    upsert_message,
    get_message,
    update_message,
    list_messages,
    delete_message,
)

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("", response_model=MessageRead, status_code=201)
async def create_message(
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await upsert_message(db, payload)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}", response_model=MessageListResponse)
async def get_messages_by_conversation(
    conversation_id: int,
    sender_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        total, items = await list_messages(
            db,
            conversation_id=conversation_id,
            sender_type=sender_type,
            limit=limit,
            offset=offset,
        )
        return MessageListResponse(total=total, items=items)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{message_id}", response_model=MessageRead)
async def get_message_detail(
    message_id: int,
    conversation_id: int = Query(..., description="ID của conversation chứa message này"),
    db: AsyncSession = Depends(get_db),
):
    try:
        msg = await get_message(db, conversation_id=conversation_id, message_id=message_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.patch("/{message_id}", response_model=MessageRead)
async def patch_message(
    message_id: int,
    conversation_id: int,
    payload: MessageUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_message(db, message_id, conversation_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{message_id}", status_code=204)
async def remove_message(
    message_id: int,
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_message(db, message_id, conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))