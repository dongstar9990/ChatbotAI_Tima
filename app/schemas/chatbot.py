from pydantic import BaseModel, Field
from typing import Optional


class ChatMessageRequest(BaseModel):
    conversation_id: Optional[int] = None
    external_conversation_id: Optional[str] = Field(None, max_length=255)
    channel_account_id: Optional[int] = None
    external_message_id: Optional[str] = Field(None, max_length=255)
    sender_id: str
    content: str


class ChatMessageResponse(BaseModel):
    conversation_id: int
    reply: str
    # messages: list[dict]


class UnansweredReplyError(BaseModel):
    conversation_id: int
    reason: str


class UnansweredReplyResponse(BaseModel):
    scanned: int
    replied: int
    skipped: int
    failed: int
    errors: list[UnansweredReplyError] = Field(default_factory=list)
