"""
Точка входа Alembic для миграций.

Здесь будет:
- настройка подключения к БД (engine),
- интеграция с SQLAlchemy models (target_metadata),
- режимы offline/online миграций.
"""

from logging.config import fileConfig
import os
from sqlalchemy import create_engine, pool
from alembic import context

from src.db.base import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _build_sync_url() -> str:
    # Prefer explicit env override
    explicit = os.getenv("ALEMBIC_SYNC_URL")
    if explicit:
        return explicit
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("DB_NAME", "summary_chatbot")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = _build_sync_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = create_engine(_build_sync_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
