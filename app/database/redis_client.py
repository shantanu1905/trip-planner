import redis
import os

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_TTL = 86400  # 2REDIS_TTL is a time-to-live value for Redis keys, i.e., the duration (in seconds) that a cached item will remain in Redis before it automatically expires.

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
