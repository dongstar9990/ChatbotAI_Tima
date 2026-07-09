from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ChannelAccountBase(BaseModel):
    name: str
    channel_id: str
    account_name: str | None = None
    external_page_id: str | None = None
    access_token: str | None = None
    status: int = 1


class ChannelAccountCreate(ChannelAccountBase):
    pass


class ChannelAccountUpdate(BaseModel):
    name: str | None = None
    channel_id: str | None = None
    account_name: str | None = None
    external_page_id: str | None = None
    access_token: str | None = None
    status: int | None = None


class ChannelAccountResponse(ChannelAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime