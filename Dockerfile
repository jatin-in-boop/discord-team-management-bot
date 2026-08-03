FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway runs this as a worker service. The migration is idempotent and runs
# before the bot process so a fresh PostgreSQL database is ready automatically.
CMD ["sh", "-c", "alembic upgrade head && exec python main.py"]