import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def build_async_db_url(
    user: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[str] = None,
    db: Optional[str] = None,
) -> str:
    user = user or os.getenv("DB_USER", "postgres")
    password = password or os.getenv("DB_PASSWORD", "postgres")
    host = host or os.getenv("DB_HOST", "localhost")
    port = port or os.getenv("DB_PORT", "5432")
    db = db or os.getenv("DB_NAME", "summary_chatbot")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def get_async_engine():
    url = build_async_db_url()
    return create_async_engine(url, future=True, echo=False)


def get_async_session_maker(engine=None) -> async_sessionmaker[AsyncSession]:
    engine = engine or get_async_engine()
    return async_sessionmaker(engine, expire_on_commit=False)
