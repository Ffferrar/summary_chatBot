"""
Модуль для загрузки конфигурации из переменных окружения.
"""

import os

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Необходимо задать API_ID, API_HASH и BOT_TOKEN через переменные окружения.")
