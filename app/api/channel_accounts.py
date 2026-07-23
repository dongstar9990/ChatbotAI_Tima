from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.schemas.channel_accounts import (
    ChannelAccountCreate,
    ChannelAccountUpdate,
    ChannelAccountResponse,
)
from app.services.channel_accounts_services import (
    get_channel_account,
    create_channel_account,
    update_channel_account,
    delete_channel_account,
    list_channel_accounts,
)

router = APIRouter(prefix="/channel-accounts", tags=["channel-accounts"])


@router.post("/", response_model=ChannelAccountResponse)
async def create_channel_account_route(
    data: ChannelAccountCreate, db: AsyncSession = Depends(get_db)
):
    return await create_channel_account(db, data)


@router.get("/")
async def list_channel_accounts_route(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    channel_id: str | None = Query(None),
    status: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    total, items = await list_channel_accounts(
        db, limit=limit, offset=offset, channel_id=channel_id, status=status
    )
    return {
        "total": total,
        "items": [ChannelAccountResponse.model_validate(i) for i in items],
    }


@router.get("/{channel_account_id}", response_model=ChannelAccountResponse)
async def get_channel_account_route(
    channel_account_id: int, db: AsyncSession = Depends(get_db)
):
    account = await get_channel_account(db, channel_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Channel account not found")
    return account


@router.patch("/{channel_account_id}", response_model=ChannelAccountResponse)
async def update_channel_account_route(
    channel_account_id: int,
    data: ChannelAccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    account = await update_channel_account(db, channel_account_id, data)
    if not account:
        raise HTTPException(status_code=404, detail="Channel account not found")
    return account


@router.delete("/{channel_account_id}")
async def delete_channel_account_route(
    channel_account_id: int, db: AsyncSession = Depends(get_db)
):
    deleted = await delete_channel_account(db, channel_account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Channel account not found")
    return {"detail": "Deleted successfully"}