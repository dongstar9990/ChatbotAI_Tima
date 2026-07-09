from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.channel_accounts import ChannelAccount
from app.schemas.channel_accounts import ChannelAccountCreate, ChannelAccountUpdate


async def get_channel_account(
    db: AsyncSession, channel_account_id: int
) -> ChannelAccount | None:
    result = await db.execute(
        select(ChannelAccount).where(ChannelAccount.id == channel_account_id)
    )
    return result.scalar_one_or_none()


async def get_channel_account_by_external_page_id(
    db: AsyncSession, external_page_id: str
) -> ChannelAccount | None:
    result = await db.execute(
        select(ChannelAccount).where(
            ChannelAccount.external_page_id == external_page_id
        )
    )
    return result.scalar_one_or_none()


async def create_channel_account(
    db: AsyncSession, data: ChannelAccountCreate
) -> ChannelAccount:
    account = ChannelAccount(
        name=data.name,
        channel_id=data.channel_id,
        account_name=data.account_name,
        external_page_id=data.external_page_id,
        access_token=data.access_token,
        status=data.status,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def update_channel_account(
    db: AsyncSession, channel_account_id: int, data: ChannelAccountUpdate
) -> ChannelAccount | None:
    account = await get_channel_account(db, channel_account_id)
    if not account:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return account


async def list_channel_accounts(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    channel_id: str | None = None,
    status: int | None = None,
) -> tuple[int, list[ChannelAccount]]:
    filters = []
    if channel_id is not None:
        filters.append(ChannelAccount.channel_id == channel_id)
    if status is not None:
        filters.append(ChannelAccount.status == status)

    count_result = await db.execute(
        select(func.count()).select_from(ChannelAccount).where(*filters)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ChannelAccount)
        .where(*filters)
        .order_by(ChannelAccount.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = result.scalars().all()
    return total, items


async def delete_channel_account(db: AsyncSession, channel_account_id: int) -> bool:
    account = await get_channel_account(db, channel_account_id)
    if not account:
        return False
    await db.delete(account)
    await db.commit()
    return True