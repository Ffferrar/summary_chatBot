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


    mistral_api_key = os.environ.get("MISTRAL_API_KEY")
    qa_service = QAService(session_factory, mistral_api_key=mistral_api_key)
    register_handlers(client, qa_service)

    async def periodic_bm25_update():
        while True:
            try:
                logger.info("[BM25] Recalculating BM25 index...")
                qa_service.rag.recalculate_bm25()
                logger.info("[BM25] BM25 index updated.")
            except Exception:
                logger.exception("[BM25] Error during BM25 update")
            await asyncio.sleep(600)  # 10 minutes

    # Start periodic BM25 update in background
    asyncio.create_task(periodic_bm25_update())

    await client.start(bot_token=BOT_TOKEN)
    logger.info("Бот запущен и ожидает сообщения…")
    try:
        await client.run_until_disconnected()
    except Exception:
        logger.exception("Bot crashed during run_until_disconnected")
        raise


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
