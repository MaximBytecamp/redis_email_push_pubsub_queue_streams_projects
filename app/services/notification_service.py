import json

from app.redis_client import NOTIFICATIONS_CHANNEL, redis_client


def publish_notification(event: str, **data: object) -> None:
    payload = {"event": event, **data}
    redis_client.publish(NOTIFICATIONS_CHANNEL, json.dumps(payload, ensure_ascii=False))
