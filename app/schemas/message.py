from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# =========================
# BASE
# =========================
class MessageBase(BaseModel):
    conversation_id:      int
    external_message_id:  Optional[str] = Field(None, max_length=255)
    sender_type:          str = Field(..., max_length=50)   # customer / agent / bot
    sender_id:            int
    message_type:         str = Field(..., max_length=50)   # text / image / file
    content:               str
    status:                Optional[str] = "sent"

# =========================
# CREATE
# =========================
class MessageCreate(MessageBase):
    pass

# =========================
# UPDATE
# =========================
class MessageUpdate(BaseModel):
    status:   Optional[str] = None
    content:  Optional[str] = None

# =========================
# READ
# =========================
class MessageRead(MessageBase):
    id:          int
    created_at:  datetime

    class Config:
        from_attributes = True

# =========================
# LIST RESPONSE (optional)
# =========================
class MessageListResponse(BaseModel):
    total: int
    items: list[MessageRead]