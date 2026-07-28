from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.db import Base


class Message(Base):
    __tablename__ = "message"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_message_id = Column(String(255), nullable=False)
    sender_type = Column(String(50), nullable=False)
    sender_id = Column(String(50), nullable=False)
    username = Column(String(255), nullable=True)
    # 1 = tin nhắn đến, 2 = tin nhắn gửi đi
    message_direction = Column(Integer, nullable=False, default=1, server_default="1")
    message_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Integer, nullable=False, default=1)

    conversation = relationship("Conversation", back_populates="messages")
