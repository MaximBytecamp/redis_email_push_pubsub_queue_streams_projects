from fastapi import APIRouter

from app.services.event_service import read_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def get_events(limit: int = 100) -> list[dict]:
    return read_events(limit=limit)
