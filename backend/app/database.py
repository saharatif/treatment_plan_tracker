"""Async SQLAlchemy engine/session setup.

`get_session` is the FastAPI dependency routers use to obtain a request-scoped
`AsyncSession`; `AsyncSessionLocal` is used directly by background jobs
(scheduler, seed scripts) that run outside the request lifecycle.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# pool_pre_ping checks connections are alive before reuse, avoiding stale-connection
# errors after the database restarts or an idle connection is dropped.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
