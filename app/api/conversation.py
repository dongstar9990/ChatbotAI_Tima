from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationRead,
    ConversationListResponse,
)
from app.services.conversation_services import (
    get_conversation,
    upsert_conversation,
    update_conversation,
    delete_conversation,
    list_conversations,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationRead)
async def create_conversation(
    data: ConversationCreate, db: AsyncSession = Depends(get_db)
):
    return await upsert_conversation(db, data)


@router.get("/", response_model=ConversationListResponse)
async def list_conversations_route(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    channel_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    total, items = await list_conversations(
        db, limit=limit, offset=offset, channel_id=channel_id
    )
    return ConversationListResponse(total=total, items=items)


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation_route(
    conversation_id: int, db: AsyncSession = Depends(get_db)
):
    convo = await get_conversation(db, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation_route(
    conversation_id: int,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    convo = await update_conversation(db, conversation_id, data)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.delete("/{conversation_id}")
async def delete_conversation_route(
    conversation_id: int, db: AsyncSession = Depends(get_db)
):
    deleted = await delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"detail": "Deleted successfully"}