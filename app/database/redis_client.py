import redis
import os
from dotenv import load_dotenv

load_dotenv()


REDIS_HOST=os.getenv("REDIS_HOST")
REDIS_PORT=os.getenv("REDIS_PORT")
REDIS_DB=os.getenv("REDIS_DB")
REDIS_TTL=os.getenv("REDIS_TTL") # 2REDIS_TTL is a time-to-live value for Redis keys, i.e., the duration (in seconds) that a cached item will remain in Redis before it automatically expires.


r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
