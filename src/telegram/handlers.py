"""
Модуль для регистрации хендлеров Telegram-бота.
"""

from telethon import events
import datetime
import logging
from src.services.qa_service import QAService

logger = logging.getLogger(__name__)


def register_handlers(client, qa_service: QAService):
    """
    Регистрирует все хендлеры для клиента Telethon.
    Обработчики команд:
    - /ask_question <текст> (а также \ask_question, /ask)
    - /show #<id> base messages (а также \show)
    """

    # Accept both slash and backslash prefixes and allow `/ask` shortcut
    ask_pattern = r'^[\\/](?:ask_question|ask)\s+(.+)'

    @client.on(events.NewMessage(pattern=ask_pattern))
    async def handle_ask_question(event):
        message_text = event.pattern_match.group(1).strip()
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)
        chat_id = event.chat_id
        timestamp = event.message.date or datetime.datetime.utcnow()
        tg_message_id = event.message.id

        logger.info("Получен запрос от %s: %s", sender_id, message_text)

        # Persist incoming message
        msg = await qa_service.record_message(
            tg_message_id=tg_message_id,
            tg_user_id=sender_id,
            chat_id=chat_id,
            timestamp=timestamp,
            text=message_text,
        )

        # Ask placeholder RAG/LLM and persist answer
        answer_text, question_id, _ = await qa_service.ask_with_placeholder(
            question_text=message_text,
            asked_by_user_id=sender_id,
            chat_id=chat_id,
            current_message_id=msg.id,
        )

        reply_text = f"question #{question_id}: {answer_text}"
        await event.reply(reply_text)

    # show pattern like `/show #3 base messages` or `\show 3`
    show_pattern = r'^[\\/]show\s+#?(\d+)'

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