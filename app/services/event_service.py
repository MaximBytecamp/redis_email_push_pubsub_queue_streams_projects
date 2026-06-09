from datetime import datetime, timezone

from app.config import settings
from app.redis_client import EVENTS_STREAM, redis_client


def write_event(event: str, **data: object) -> str:
    payload = {
        "event": event,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **{key: "" if value is None else str(value) for key, value in data.items()},
    }
    return redis_client.xadd(EVENTS_STREAM, payload, maxlen=settings.events_stream_maxlen, approximate=True)


def read_events(limit: int = 100, mailing_id: int | None = None) -> list[dict]:
    rows = redis_client.xrevrange(EVENTS_STREAM, count=limit)
    events: list[dict] = []
    for event_id, data in rows:
        if mailing_id is not None and data.get("mailing_id") != str(mailing_id):
            continue
        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except ValueError:
                created_at = None
        events.append(
            {
                "id": event_id,
                "event": data.get("event", ""),
                "created_at": created_at,
                "data": data,
            }
        )
    return events
