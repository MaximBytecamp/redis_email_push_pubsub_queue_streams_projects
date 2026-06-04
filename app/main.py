import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.redis_client import NOTIFICATIONS_CHANNEL, redis_client
from app.routers import events, imports, mailings, recipients

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Email Mailing Service", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/notifications/stream")
def notifications_stream() -> StreamingResponse:
    def event_generator():
        pubsub = redis_client.pubsub()
        pubsub.subscribe(NOTIFICATIONS_CHANNEL)
        try:
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = message["data"]
                yield f"data: {payload}\n\n"
        except GeneratorExit:
            pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
def health() -> dict:
    try:
        redis_client.ping()
        redis_status = "ok"
    except Exception as exc:
        redis_status = f"error: {exc}"
    return {"status": "ok", "redis": redis_status}


app.include_router(recipients.router)
app.include_router(mailings.router)
app.include_router(events.router)
