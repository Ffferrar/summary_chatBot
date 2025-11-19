from __future__ import annotations

from typing import Iterable, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.db import Base
from src.db.models import Message, Answer, answer_base_messages


from src.rag.telegram_rag import TelegramRAGSystem
import os

class QAService:
    def __init__(self, session_factory, rag_system: TelegramRAGSystem = None, mistral_api_key: str = None):
        """
        session_factory: async sessionmaker instance (e.g. sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False))
        rag_system: instance of TelegramRAGSystem (optional, will be created if not provided)
        mistral_api_key: API key for Mistral LLM (optional, can be set via env MISTRAL_API_KEY)
        """
        self._session_factory = session_factory
        if rag_system is not None:
            self.rag = rag_system
        else:
            api_key = mistral_api_key or os.environ.get("MISTRAL_API_KEY")
            self.rag = TelegramRAGSystem(mistral_api_key=api_key)

    async def record_message(
        self,
        *,
        tg_message_id: int,
        tg_user_id: int,
        chat_id: int,
        timestamp,
        text: str,
        username: Optional[str] = None,
    ) -> Message:
        async with self._session_factory() as session:
            msg = Message(
                tg_message_id=tg_message_id,
                tg_user_id=tg_user_id,
                chat_id=chat_id,
                timestamp=timestamp,
                text=text,
            )
            session.add(msg)
            try:
                await session.commit()
            except Exception:
                # If commit fails (e.g. concurrent insert / integrity error), rollback and try to fetch existing
                await session.rollback()
                existing = await session.execute(
                    select(Message).where(
                        Message.chat_id == chat_id,
                        Message.tg_message_id == tg_message_id,
                    )
                )
                existing_msg = existing.scalar_one_or_none()
                if existing_msg:
                    # Also log to Qdrant if not already present
                    self._log_to_qdrant(existing_msg, username=username)
                    return existing_msg
                # Re-raise if it's an unexpected error
                raise
            await session.refresh(msg)
            # Log to Qdrant/BM25
            self._log_to_qdrant(msg, username=username)
            return msg

    def _log_to_qdrant(self, msg: Message, username: Optional[str] = None):
        # Add message to Qdrant/BM25 index
        doc = {
            "id": msg.id,
            "text": msg.text,
            "user_id": str(msg.tg_user_id),
            "timestamp": msg.timestamp.timestamp() if hasattr(msg.timestamp, 'timestamp') else float(msg.timestamp),
            "username": username,
        }
        self.rag.add_documents([doc])

    async def create_answer(
        self,
        *,
        question_text: str,
        answer_text: str,
        asked_by_user_id: int,
        chat_id: int,
        base_message_ids: Iterable[int],
        tg_answer_message_id: int | None = None,
    ) -> Answer:
        async with self._session_factory() as session:
            ans = Answer(
                question_text=question_text,
                answer_text=answer_text,
                asked_by_user_id=asked_by_user_id,
                chat_id=chat_id,
                tg_answer_message_id=tg_answer_message_id,
            )
            session.add(ans)
            await session.flush()  # get id

            for mid in base_message_ids:
                await session.execute(
                    answer_base_messages.insert().values(answer_id=ans.id, message_id=mid)
                )

            await session.commit()
            await session.refresh(ans)
            return ans

    async def get_base_messages(self, answer_id: int) -> List[Message]:
        async with self._session_factory() as session:
            stmt = (
                select(Message)
                .join(answer_base_messages, answer_base_messages.c.message_id == Message.id)
                .where(answer_base_messages.c.answer_id == answer_id)
                .order_by(Message.timestamp.asc())
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())


    async def ask_with_rag_llm(
        self,
        *,
        question_text: str,
        asked_by_user_id: int,
        chat_id: int,
        top_k: int = 5,
        current_message_id: int = None,
        mistral_api_key: str = None,
    ) -> Tuple[str, int, list[int]]:
        """
        Perform RAG search and LLM answer generation. Returns (answer_text, answer_id, base_message_ids).
        """
        # Search for relevant messages in Qdrant/BM25
        results = self.rag.search(question_text, k=top_k)
        doc_ids = [doc_id for doc_id, _ in results]
        # Get texts for those messages
        doc_texts = self.rag.get_document_texts(doc_ids)
        # Format for LLM
        messages = [(doc_id, text) for doc_id, text in doc_texts]
        # Call LLM
        answer_text = self.rag.run_mistral(question_text, messages, api_key=mistral_api_key)
        # Map doc_ids to Message DB ids (they are DB ids)
        base_message_ids = [int(doc_id) for doc_id, _ in doc_texts if str(doc_id).isdigit()]
        # Save answer
        ans = await self.create_answer(
            question_text=question_text,
            answer_text=answer_text,
            asked_by_user_id=asked_by_user_id,
            chat_id=chat_id,
            base_message_ids=base_message_ids,
        )
        return answer_text, ans.id, base_message_ids

    async def ask_with_placeholder(
        self,
        *,
        question_text: str,
        asked_by_user_id: int,
        chat_id: int,
        current_message_id: int,
    ) -> Tuple[str, int, list[int]]:
        """
        Calls ask_with_rag_llm for real RAG/LLM answer. Returns (answer_text, answer_id, base_message_ids).
        """
        return await self.ask_with_rag_llm(
            question_text=question_text,
            asked_by_user_id=asked_by_user_id,
            chat_id=chat_id,
            current_message_id=current_message_id,
        )

    async def get_message_by_tg_id(self, chat_id: int, tg_message_id: int) -> Message | None:
        async with self._session_factory() as session:
            stmt = select(Message).where(
                Message.chat_id == chat_id,
                Message.tg_message_id == tg_message_id,
            )
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def get_answer_by_id(self, answer_id: int) -> Answer | None:
        async with self._session_factory() as session:
            stmt = select(Answer).where(Answer.id == answer_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()
