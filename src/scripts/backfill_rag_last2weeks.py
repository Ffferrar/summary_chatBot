"""
Script to backfill all messages from the last 2 weeks in a chat to the RAG DB.
Usage:
  python -m src.scripts.backfill_rag_last2weeks <chat_id>
"""
import os
import asyncio
import datetime
from telethon import TelegramClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.telegram.config import API_ID, API_HASH, BOT_TOKEN
from src.services.qa_service import QAService

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "summary_chatbot")
ASYNC_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def backfill(chat_id: int):
    engine = create_async_engine(ASYNC_DB_URL, echo=False, future=True)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    qa_service = QAService(session_factory)
    client = TelegramClient("bot", int(API_ID), API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    two_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)
    print(f"Fetching messages for chat {chat_id} since {two_weeks_ago}...")
    count = 0
    async for msg in client.iter_messages(chat_id, min_id=0, offset_date=two_weeks_ago, reverse=True):
        if not msg.text:
            continue
        await qa_service.record_message(
            tg_message_id=msg.id,
            tg_user_id=msg.sender_id or 0,
            chat_id=chat_id,
            timestamp=msg.date,
            text=msg.text,
        )
        count += 1
        if count % 100 == 0:
            print(f"Indexed {count} messages...")
    print(f"Done. Indexed {count} messages from last 2 weeks.")
    await client.disconnect()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.scripts.backfill_rag_last2weeks <chat_id>")
        exit(1)
    chat_id = int(sys.argv[1])
    asyncio.run(backfill(chat_id))
