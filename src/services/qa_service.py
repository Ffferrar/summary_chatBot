from __future__ import annotations

from typing import Iterable, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.db import Base
from src.db.models import Message, Answer, answer_base_messages


class QAService:
    def __init__(self, session_factory):
        """
        session_factory: async sessionmaker instance (e.g. sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False))
        """
        self._session_factory = session_factory

    async def record_message(
        self,
        *,
        tg_message_id: int,
        tg_user_id: int,
        chat_id: int,
        timestamp,
        text: str,
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
            await session.commit()
            await session.refresh(msg)
            return msg

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

    async def ask_with_placeholder(
        self,
        *,
        question_text: str,
        asked_by_user_id: int,
        chat_id: int,
        current_message_id: int,
    ) -> Tuple[str, int, list[int]]:
        """
        Placeholder for RAG/LLM: returns a dummy answer and uses the current message as the only base message.
        Returns (answer_text, answer_id, base_message_ids).
        """
        answer_text = "here is the link (placeholder)"
        base_message_ids = [current_message_id]
        ans = await self.create_answer(
            question_text=question_text,
            answer_text=answer_text,
            asked_by_user_id=asked_by_user_id,
            chat_id=chat_id,
            base_message_ids=base_message_ids,
        )
        return answer_text, ans.id, base_message_ids
