from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None           
    external_conversation_id: Optional[str] = Field(None, max_length=255)
    sender_id: int
    content: str


class ChatResponse(BaseModel):
    conversation_id: int
    user_message_id: int
    bot_message_id: int
    reply: str