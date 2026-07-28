from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.schemas.message import (
    MessageCreate,
    MessageRead,
    MessageListResponse,
    SendMessageRequest,
)
from app.services.facebook_services import FacebookSendError, send_facebook_text
from app.services.message_services import upsert_message, list_messages
from app.services.channel_accounts_services import get_channel_account
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
    channel_account_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    total, items = await list_conversations(
        db, limit=limit, offset=offset, channel_account_id=channel_account_id
    )
    return ConversationListResponse(total=total, items=items)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_conversation_messages(
    conversation_id: int,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sender_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách message theo conversation, có phân trang."""
    convo = await get_conversation(db, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    total, items = await list_messages(
        db,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
        sender_type=sender_type,
    )
    return MessageListResponse(total=total, items=items)


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


@router.post("/{conversation_id}/send", response_model=MessageRead, status_code=201)
async def send_message_to_facebook(
    conversation_id: int,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Gửi text tới người dùng Messenger của conversation này."""
    convo = await get_conversation(db, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not convo.external_conversation_id:
        raise HTTPException(status_code=400, detail="Conversation thiếu PSID người nhận")
    if not convo.channel_account_id:
        raise HTTPException(status_code=400, detail="Conversation chưa có channel account")

    account = await get_channel_account(db, convo.channel_account_id)
    if not account or account.status != 1:
        raise HTTPException(status_code=400, detail="Facebook channel account không hợp lệ hoặc chưa được kích hoạt ")
    if not account.external_page_id or not account.access_token:
        raise HTTPException(status_code=500, detail="Thiếu external_page_id hoặc access_token")

    try:
        external_message_id = await send_facebook_text(
            page_id=account.external_page_id,
            access_token=account.access_token,
            recipient_id=convo.external_conversation_id,
            text=payload.content,
        )
    except FacebookSendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return await upsert_message(
        db,
        MessageCreate(
            conversation_id=conversation_id,
            external_message_id=external_message_id,
            sender_type="agent",
            sender_id=convo.external_conversation_id,
            username=payload.username,
            message_direction=1,
            message_type="text",
            content=payload.content,
            status=1,
        ),
    )
