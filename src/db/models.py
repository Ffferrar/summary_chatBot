from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Backrefs
    used_in_answers: Mapped[list[Answer]] = relationship(
        back_populates="base_messages",
        secondary=lambda: answer_base_messages,
        viewonly=True,
    )


answer_base_messages: Table = Table(
    "answer_base_messages",
    Base.metadata,
    Column("answer_id", ForeignKey("answers.id", ondelete="CASCADE"), primary_key=True),
    Column("message_id", ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)  # question ID
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    asked_by_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tg_answer_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    base_messages: Mapped[list[Message]] = relationship(
        secondary=lambda: answer_base_messages,
        back_populates="used_in_answers",
        lazy="selectin",
    )
