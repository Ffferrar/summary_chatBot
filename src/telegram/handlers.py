"""
Модуль для регистрации хендлеров Telegram-бота.
"""

from telethon import events
import datetime
import logging

logger = logging.getLogger(__name__)

def register_handlers(client):
    """
    Регистрирует все хендлеры для клиента Telethon.
    """
    @client.on(events.NewMessage(pattern=r'^/ask\s+(.+)'))
    async def handle_ask(event):
        """
        Хендлер для обработки команды /ask.
        """
        message_text = event.pattern_match.group(1)
        sender = await event.get_sender()
        sender_name = f"{sender.first_name} {sender.last_name or ''}".strip()
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"Получено сообщение: {message_text} от {sender_name} в {timestamp}")

        await event.reply(f"Ваш запрос принят!\n\nТекст: {message_text}\nАвтор: {sender_name}\nВремя: {timestamp}")