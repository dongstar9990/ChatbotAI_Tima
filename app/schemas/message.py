from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MessageBase(BaseModel):
    conversation_id: int
    external_message_id: Optional[str] = Field(None, max_length=255)
    sender_type: str = Field(..., max_length=50)   # customer / agent / bot
    sender_id: int
    message_type: str = Field(..., max_length=50)  # text / image / file
    content: str
    status: Optional[int] = 1


class MessageCreate(MessageBase):
    pass


class MessageUpdate(BaseModel):
    status: Optional[int] = None
    content: Optional[str] = None


class MessageRead(MessageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    total: int
    items: list[MessageRead]