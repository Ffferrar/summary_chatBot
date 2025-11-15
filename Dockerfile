# Dockerfile для сборки контейнера с приложением.
# Позже сюда добавим:
# - установку зависимостей (poetry/pip)
# - копирование src/
# - команду запуска (python -m tg_rag_bot.main)

FROM python:3.12-slim

WORKDIR /app

# TODO: скопировать pyproject.toml / requirements.txt и src/
# TODO: установить зависимости
# TODO: задать CMD для запуска бота
