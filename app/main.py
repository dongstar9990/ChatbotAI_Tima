from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.db import Base, engine
from app.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tạo bảng khi app khởi động (chỉ dùng cho dev/demo)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Chat Service", lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}