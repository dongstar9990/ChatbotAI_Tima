from sqlalchemy import Column, Integer, String, DateTime , ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.db import Base


class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, index=True)
    channel_account_id = Column(
        Integer,
        ForeignKey("channel_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_conversation_id = Column(String(255), nullable=True)
    status = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="conversation", cascade="save-update, merge" ,passive_deletes=True)
    channel_account = relationship("ChannelAccount", back_populates="conversations")
