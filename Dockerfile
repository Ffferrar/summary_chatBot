FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* /app/

RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

COPY src/ /app/src/

CMD ["python", "src/main.py"]
