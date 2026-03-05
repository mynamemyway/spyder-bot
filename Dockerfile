# Dockerfile
FROM python:3.12-slim

# Установим зависимости ОС, если вдруг понадобятся (для некоторых пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Переменные окружения для Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код — сохраняем структуру!
COPY app ./app
COPY main.py .
COPY assets ./assets

# Создаем векторный индекс на этапе сборки.
# Это гарантирует, что образ содержит готовый к работе индекс.
# Для этого шага требуется доступ к переменным окружения.

# Объявляем аргументы сборки, которые будут переданы из docker-compose.yml
ARG BOT_TOKEN
ARG OPENROUTER_API_KEY
ARG EMBEDDING_SERVICE_URL
ARG MANAGER_TELEGRAM_URL

# Устанавливаем аргументы как переменные окружения, чтобы они были доступны для команды RUN
ENV BOT_TOKEN=${BOT_TOKEN}
ENV OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
ENV EMBEDDING_SERVICE_URL=${EMBEDDING_SERVICE_URL}
ENV MANAGER_TELEGRAM_URL=${MANAGER_TELEGRAM_URL}

RUN python -m app.core.rag

CMD ["python", "main.py"]