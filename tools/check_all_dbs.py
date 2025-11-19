"""
Check that messages are present in all storages: Postgres, Qdrant (embeddings & bm25).
Usage:
  python tools/check_all_dbs.py <chat_id>
"""
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.db.models import Message
from src.services.qa_service import QAService
from src.rag.telegram_rag import TelegramRAGSystem

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "summary_chatbot")
ASYNC_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def main(chat_id: int):
    # Check Postgres
    engine = create_async_engine(ASYNC_DB_URL, echo=False, future=True)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        res = await session.execute(
            Message.__table__.select().where(Message.chat_id == chat_id)
        )
        messages = res.fetchall()
        print(f"Postgres: {len(messages)} messages for chat {chat_id}")
        if messages:
            print("First message:", dict(messages[0]._mapping))

    # Check Qdrant
    from src.rag.telegram_rag import QDRANT_COLLECTION_EMBEDDINGS, QDRANT_COLLECTION_BM25
    rag = TelegramRAGSystem()
    # Embeddings
    points_emb = rag.qdrant_embeddings.scroll(collection_name=QDRANT_COLLECTION_EMBEDDINGS, limit=5)[0]
    print(f"Qdrant embeddings: {len(points_emb)} example points")
    if points_emb:
        print("First point:", points_emb[0].payload)
    # BM25
    points_bm = rag.qdrant_bm25.scroll(collection_name=QDRANT_COLLECTION_BM25, limit=5)[0]
    print(f"Qdrant BM25: {len(points_bm)} example points")
    if points_bm:
        print("First point:", points_bm[0].payload)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tools/check_all_dbs.py <chat_id>")
        exit(1)
    chat_id = int(sys.argv[1])
    asyncio.run(main(chat_id))
