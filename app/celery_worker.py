from celery import Celery
import os 
from dotenv import load_dotenv

load_dotenv()


# Load Redis connection details from environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Construct Redis URL
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Create Celery app
celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL,  # Optional: store task results
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_concurrency=4,  # Adjust based on CPU cores
    task_track_started=True,
    task_time_limit=300,   # Timeout in seconds
)


# Auto-discover tasks from your app.tasks folder
celery_app.autodiscover_tasks(["app.task"])
