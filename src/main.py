"""
Точка входа для Telegram-бота.

Шаги запуска:
- загрузка конфигурации
- настройка логирования
- подключение к БД (async SQLAlchemy)
- запуск Telethon-клиента и регистрация хендлеров
"""

import asyncio
import os
import logging

from telethon import TelegramClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.telegram.config import API_ID, API_HASH, BOT_TOKEN
from src.telegram.logging_config import setup_logging
from src.services.qa_service import QAService
from src.telegram.handlers import register_handlers


DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "summary_chatbot")

ASYNC_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


async def async_main():
    setup_logging()
    logger = logging.getLogger(__name__)

    # DB
    engine = create_async_engine(ASYNC_DB_URL, echo=False, future=True)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Telethon
    client = TelegramClient("bot", int(API_ID), API_HASH)
    await client.start(bot_token=BOT_TOKEN)

    qa_service = QAService(session_factory)
    register_handlers(client, qa_service)

    logger.info("Бот запущен и ожидает сообщения…")
    await client.run_until_disconnected()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
