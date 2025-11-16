"""
Точка входа для Telegram-бота.

TODO: создание подключения к БД.
"""

from telethon import TelegramClient
import logging
from logging_config import setup_logging
from handlers import register_handlers
from config import API_ID, API_HASH, BOT_TOKEN

setup_logging()
logger = logging.getLogger(__name__)

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logger.info("Telegram бот успешно запущен.")

register_handlers(client)

if __name__ == '__main__':
    try:
        logger.info("Бот запущен и ожидает сообщений...")
        client.run_until_disconnected()
    except Exception as e:
        logger.exception("Произошла ошибка при работе бота: %s", e)
