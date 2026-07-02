from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# =========================
# BASE
# =========================
class ConversationBase(BaseModel):
    external_conversation_id: Optional[str] = Field(None, max_length=255)
    status: Optional[int] = 1

# =========================
# CREATE
# =========================
class ConversationCreate(ConversationBase):
    pass

# =========================
# UPDATE
# =========================
class ConversationUpdate(BaseModel):
    external_conversation_id: Optional[str] = Field(None, max_length=255)
    status: Optional[int] = None

# =========================
# READ
# =========================
class ConversationRead(ConversationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# =========================
# LIST RESPONSE
# =========================
class ConversationListResponse(BaseModel):
    total: int
    items: list[ConversationRead]