"""
Точка входа Alembic для миграций.

Здесь будет:
- настройка подключения к БД (engine),
- интеграция с SQLAlchemy models (target_metadata),
- режимы offline/online миграций.
"""

from logging.config import fileConfig
from alembic import context

# TODO: импортировать Base из src.tg_rag_bot.db.base и подставить metadata
# from tg_rag_bot.db.base import Base

config = context.config
fileConfig(config.config_file_name)

target_metadata = None  # TODO: заменить на Base.metadata


def run_migrations_offline():
    """Запуск миграций в offline-режиме (генерация SQL без прямого коннекта)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Запуск миграций в online-режиме (прямое подключение к БД)."""
    # TODO: создать engine на основе sqlalchemy.url и выполнить миграции


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
