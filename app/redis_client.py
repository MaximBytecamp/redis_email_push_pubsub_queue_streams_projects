import redis

from app.config import settings


IMPORT_QUEUE = "imports:queue"
EMAIL_QUEUE = "email:queue"
NOTIFICATIONS_CHANNEL = "notifications"
EVENTS_STREAM = "system:events"


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


redis_client = get_redis()
