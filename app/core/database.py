from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings

# Convert SQLite URL to async format
if settings.database_url.startswith("sqlite:///"):
    async_database_url = settings.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    async_database_url = settings.database_url

# Create async database engine
engine = create_async_engine(
    async_database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in async_database_url else {}
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Create base class for models
Base = declarative_base()

async def get_db():
    """Dependency to get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)