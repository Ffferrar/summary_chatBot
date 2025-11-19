"""
Модуль для регистрации хендлеров Telegram-бота.
"""

from telethon import events
from telethon.tl import types
import re
import datetime
import logging
from src.services.qa_service import QAService

logger = logging.getLogger(__name__)


def register_handlers(client, qa_service: QAService):
    r"""
    Регистрирует все хендлеры для клиента Telethon.
    Обработчики команд:
    - /ask_question <текст> (а также \\ask_question, /ask)
    - /show #<id> base messages (а также \\show)
    """

    # Accept both slash and backslash prefixes and allow `/ask` shortcut
    ask_pattern = r'^[\\/](?:ask_question|ask)\s+(.+)'
    ASK_RE = re.compile(ask_pattern)

    @client.on(events.NewMessage(pattern=ask_pattern))
    async def handle_ask_question(event):
        try:
            message_text = event.pattern_match.group(1).strip()
            sender_id = _extract_author_id(event)
            chat_id = event.chat_id
            timestamp = event.message.date or datetime.datetime.utcnow()
            tg_message_id = event.message.id

            logger.info("Получен запрос от %s: %s", sender_id, message_text)

            # Получить уже залогированное сообщение (capture_all_messages должен был его залогировать)
            msg = await qa_service.get_message_by_tg_id(chat_id, tg_message_id)
            if not msg:
                # Если не найдено, залогировать (на всякий случай)
                msg = await qa_service.record_message(
                    tg_message_id=tg_message_id,
                    tg_user_id=sender_id,
                    chat_id=chat_id,
                    timestamp=timestamp,
                    text=event.raw_text or message_text,
                )

            # Use RAG/LLM for answer
            try:
                answer_text, question_id, _ = await qa_service.ask_with_rag_llm(
                    question_text=message_text,
                    asked_by_user_id=sender_id,
                    chat_id=chat_id,
                    current_message_id=msg.id,
                )
                reply_text = f"question #{question_id}: {answer_text}"
                await event.reply(reply_text)
            except Exception as e:
                logger.exception("RAG/LLM error in handle_ask_question")
                await event.reply("Произошла ошибка при генерации ответа через LLM. Попробуйте позже.")
        except Exception:
            logger.exception("Unhandled exception on handle_ask_question (outer)")
            try:
                await event.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")
            except Exception:
                logger.debug("Failed to send error reply to user")

    # show pattern like `/show #3 base messages` or `\show 3`
    show_pattern = r'^[\\/]show\s+#?(\d+)'
    SHOW_RE = re.compile(show_pattern)

    @client.on(events.NewMessage(pattern=show_pattern))
    async def handle_show(event):
        question_id_raw = event.pattern_match.group(1)
        try:
            question_id = int(question_id_raw)
        except ValueError:
            await event.reply("Некорректный идентификатор вопроса.")
            return

        base_msgs = await qa_service.get_base_messages(question_id)
        if not base_msgs:
            await event.reply("Базовые сообщения не найдены для указанного вопроса.")
            return

        await event.reply(f"Пересылаю базовые сообщения для #{question_id}…")
        try:
            tg_ids = [m.tg_message_id for m in base_msgs]
            await event.client.forward_messages(event.chat_id, tg_ids)
        except Exception:
            # Fallback to plaintext resend
            for m in base_msgs:
                preview = (m.text or "").strip()
                if len(preview) > 4096:
                    preview = preview[:4000] + "\n…(обрезано)…"
                await event.reply(preview or "<пустое сообщение>")

    @client.on(events.NewMessage(incoming=True))
    async def debug_any_message(event):
        print("DEBUG ANY MESSAGE:", event.chat_id, repr(event.raw_text))

    @client.on(events.NewMessage(incoming=True))
    async def capture_all_messages(event):
        """
        Логируем все новые входящие сообщения в группах/каналах (кроме сообщений бота).
        """
        try:
            logger.debug(
                "New message (capture_all_messages): chat_id=%s, is_group=%s, is_channel=%s, is_private=%s, out=%s",
                event.chat_id,
                getattr(event, "is_group", None),
                getattr(event, "is_channel", None),
                getattr(event, "is_private", None),
                getattr(event, "out", None),
            )

            # 1) пропускаем собственные сообщения бота
            if event.out:
                return

            # 2) нас интересуют только групповые чаты / каналы
            is_group = bool(getattr(event, "is_group", False))
            is_channel = bool(getattr(event, "is_channel", False))
            if not (is_group or is_channel):
                # если вдруг захочешь писать ещё и лички с ботом — просто убери этот return
                return

            text = event.raw_text or ""
            sender_id = _extract_author_id(event)

            logger.info(
                "Captured message from %s in chat %s: %s",
                sender_id,
                event.chat_id,
                text[:100],
            )

            await qa_service.record_message(
                tg_message_id=event.message.id,
                tg_user_id=sender_id,
                chat_id=event.chat_id,
                timestamp=event.message.date or datetime.datetime.utcnow(),
                text=text,
            )
        except Exception:
            logger.exception("capture_all_messages error")

def _extract_author_id(event) -> int:
    """
    Возвращает ID автора сообщения.
    - user: sender_id / from_id.user_id
    - анонимный админ / пост канала: используем chat_id как суррогат
    """
    if getattr(event, "sender_id", None) is not None:
        return int(event.sender_id)
    f = getattr(event.message, "from_id", None)
    if isinstance(f, types.PeerUser):
        return int(f.user_id)
    if isinstance(f, types.PeerChannel):
        return int(event.chat_id)
    return int(event.chat_id)