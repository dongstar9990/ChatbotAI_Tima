from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ConversationBase(BaseModel):
    external_conversation_id: str = Field(..., max_length=255)
    channel_account_id: Optional[int] = None
    status: Optional[int] = 1


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    external_conversation_id: Optional[str] = Field(None, max_length=255)
    channel_account_id: Optional[int] = None
    status: Optional[int] = 1


class ConversationRead(ConversationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    total: int
    items: list[ConversationRead]