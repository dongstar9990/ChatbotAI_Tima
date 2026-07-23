from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import DATABASE_URL , DEBUG
from typing import AsyncGenerator

# ==================== Base cho Models ====================
class Base(DeclarativeBase):
    """Base class dùng cho tất cả models (Tenant, User, ...)"""
    pass


# ==================== Engine & Session ====================

engine = create_async_engine(
    DATABASE_URL,
    echo=DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ==================== Dependency get_db ====================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency chính dùng trong API routes"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ==================== Init & Close ====================
async def init_db():
    """Gọi khi app startup"""
    try:
        async with engine.connect() as conn:
            # Kiểm tra kết nối
            await conn.execute(text("SELECT 1"))
            print("✅ Database connected successfully (SQLAlchemy Async)")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise


async def close_db():
    """Gọi khi app shutdown"""
    await engine.dispose()
    print("🛑 Database connection closed")