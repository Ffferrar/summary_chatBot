# Closed AI Telegram Bot

RAG‑бот для Telegram, который:

- слушает сообщения в групповых чатах,
- логирует их в PostgreSQL,
- индексирует в Qdrant (векторный поиск + BM25),
- отвечает на вопросы по истории чата с помощью LLM (Mistral).

Проект заточен под реальный групповой чат, а не 1‑1 диалоги.

---

## Архитектура

### Основные компоненты

- **Telegram-бот**  
  - Библиотека: `telethon`  
  - Обработка команд и сообщений: `src/telegram/handlers.py`  
  - Точка входа: `src/main.py`

- **PostgreSQL (источник правды)**  
  - Хранит: `messages`, `answers`, `answer_base_messages`.  
  - ORM: `SQLAlchemy 2.x`  
  - Миграции: `Alembic`

- **RAG-слой (Qdrant + BM25 + эмбеддинги)**  
  - Модуль: `src/rag/telegram_rag.py` (`TelegramRAGSystem`)  
  - Векторное хранилище: `Qdrant` (docker‑сервис)  
  - Эмбеддинги: `sentence-transformers/all-MiniLM-L6-v2`  
  - Текстовый поиск: `BM25Okapi` (`rank-bm25`)

- **LLM‑слой (Mistral)**  
  - Клиент: `mistralai`  
  - Модель по умолчанию: `mistral-medium-latest`

- **Сервисный слой**  
  - `src/services/qa_service.py` — логика записи сообщений, интеграция RAG и LLM.

---

## Основной сценарий работы

1. Бот получает сообщение в группe:
   - пишет запись в Postgres (`messages`),
   - добавляет точку в Qdrant: эмбеддинг в `telegram_embeddings` и payload в `telegram_bm25`.
2. При запросе `/ask_question <текст>`:
   - `QAService.ask_with_rag_llm` делает RAG (векторный поиск + BM25),
   - формирует промпт из релевантных сообщений и отправляет в Mistral,
   - сохраняет ответ в `answers` и связь с базовыми сообщениями.

---

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и заполните параметры (Telegram, Postgres, Mistral):

```env
API_ID=...
API_HASH=...
BOT_TOKEN=...

DB_HOST=db
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=summary_chatbot

MISTRAL_API_KEY=...
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

2. Запуск через Docker Compose:

```bash
docker-compose up -d --build
```

3. Примените миграции (создание таблиц):

```bash
docker-compose exec app alembic upgrade head
```

4. Посмотреть логи бота:

```bash
docker-compose logs -f app
```

---

## Команды бота

- `/ask_question <текст>` или `/ask <текст>` — задать вопрос по истории чата.
- `/show #<id>` — показать базовые сообщения, использованные при ответе с id `#<id>`.

---

## Проверка наличия данных во всех БД

Используйте скрипт `tools/check_all_dbs.py` для проверки:

```bash
docker-compose exec app python tools/check_all_dbs.py <chat_id>
```

Скрипт покажет количество сообщений в Postgres и примеры точек в Qdrant.

---

## Обновление эмбеддингов и BM25

- Новые сообщения индексируются сразу при записи (`TelegramRAGSystem.add_documents`).
- BM25 индекс пересобирается периодически (фоновая задача в `src/main.py`, по умолчанию раз в 10 минут) через `recalculate_bm25()`.
- При смене модели эмбеддингов создайте отдельный скрипт для пересчёта всех эмбеддингов.

---

## Частые проблемы и рекомендации

- `relation "messages" does not exist` — не применены миграции (см. раздел миграций выше).
- Предупреждения PyTorch/MKL на aarch64 (например, `Can't read MIDR_EL1 sysfs entry`) можно игнорировать — это про оптимизации CPU.
- Qdrant предупреждает об использовании FUSE‑файловых систем — в dev это обычно безопасно, но для продакшна используйте нативный docker volume.
==