from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.db import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationRead,
    ConversationListResponse,
)
from app.services.conversation_services import (
    upsert_conversation,
    get_conversation,
    update_conversation,
    list_conversations,
    delete_conversation,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await upsert_conversation(db, payload)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ConversationListResponse)
async def get_conversations(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        total, items = await list_conversations(
            db, status=status, limit=limit, offset=offset
        )
        return ConversationListResponse(total=total, items=items)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation_detail(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        convo = await get_conversation(db, conversation_id=conversation_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def patch_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_conversation(db, conversation_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}", status_code=204)
async def remove_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_conversation(db, conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))