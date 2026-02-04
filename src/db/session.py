"""Async SQLAlchemy database session configuration for Supabase."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import settings

# Supabase connection settings:
# - Use NullPool for Transaction Pooler (port 6543) - REQUIRED
# - Supabase Pooler handles connection pooling, so we don't need SQLAlchemy pooling
# - SSL is handled by Supabase automatically

# Build connection args
connect_args = {}

# For Supabase Transaction Pooler compatibility
if "pooler.supabase.com" in settings.database_url:
    # Different drivers need different parameters:
    # - asyncpg: prepared_statement_cache_size=0
    # - psycopg: prepare_threshold=0 (or no special config needed)
    if "asyncpg" in settings.database_url:
        connect_args["prepared_statement_cache_size"] = 0
    elif "psycopg" in settings.database_url:
        # psycopg with Supabase Pooler - no special config needed
        # Pooler handles this automatically
        pass

# Create async engine
# NullPool is REQUIRED for Supabase Transaction Pooler (port 6543)
engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    poolclass=NullPool,  # Required for Supabase/serverless
    connect_args=connect_args,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for use outside of FastAPI routes (e.g., in scheduler jobs).

    Usage:
        async with get_db_context() as db:
            tenders = await db.execute(select(Tender))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
