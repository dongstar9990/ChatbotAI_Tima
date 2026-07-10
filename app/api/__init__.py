from fastapi import APIRouter

from app.api import conversation, message , chatbot ,channel_accounts

api_router = APIRouter()

api_router.include_router(conversation.router)

api_router.include_router(message.router)

api_router.include_router(chatbot.router)

api_router.include_router(channel_accounts.router)