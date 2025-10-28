# ===========================
# AI Trip Planner - Dockerfile
# ===========================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Run both FastAPI and Celery in parallel
CMD bash -c "uvicorn app.main:app --host 0.0.0.0 --port 8000 & \
    celery -A app.celery_worker.celery_app worker --loglevel=info --pool=solo & \
    wait"
