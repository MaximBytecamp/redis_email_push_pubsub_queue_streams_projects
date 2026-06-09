import logging
import time

from app.config import settings
from app.database import SessionLocal, init_db
from app.services.watchdog_service import run_watchdog_once
from app.workers.runner import configure_logging


def main() -> None:
    configure_logging()
    logger = logging.getLogger("watchdog_worker")

    init_db()
    logger.info(
        "started; stale threshold=%ss interval=%ss",
        settings.watchdog_stale_seconds,
        settings.watchdog_interval_seconds,
    )

    while True:
        db = SessionLocal()
        try:
            result = run_watchdog_once(db)
            total_failed = sum(result.values())
            if total_failed:
                logger.info("marked stale tasks as failed: %s", result)
        except Exception:
            logger.exception("watchdog iteration failed")
        finally:
            db.close()

        time.sleep(settings.watchdog_interval_seconds)


if __name__ == "__main__":
    main()
