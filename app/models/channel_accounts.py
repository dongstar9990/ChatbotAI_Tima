from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.db import Base


class ChannelAccount(Base):
    __tablename__ = "channel_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    channel_id = Column(String(255), nullable=False)
    account_name = Column(String(255), nullable=True)
    external_page_id = Column(String(255), nullable=True)
    access_token = Column(String(500), nullable=True)
    status = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversations = relationship(
        "Conversation",
        back_populates="channel_account",
        cascade="save-update, merge",
        passive_deletes=True,
    )