from pydantic import BaseModel, Field
from typing import Optional


class ChatMessageRequest(BaseModel):
    conversation_id: Optional[int] = None
    external_conversation_id: Optional[str] = Field(None, max_length=255)
    external_message_id: Optional[str] = Field(None, max_length=255)
    sender_id: str
    content: str


class ChatMessageResponse(BaseModel):
    conversation_id: int
    reply: str
    # messages: list[dict]