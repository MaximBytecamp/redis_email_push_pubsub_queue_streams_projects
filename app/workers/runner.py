import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db

WaitForTask = Callable[[int], int | None]
ProcessTask = Callable[[Session, int], object]


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def run_worker(
    *,
    name: str,
    queue_name: str,
    wait_for_task: WaitForTask,
    process_task: ProcessTask,
    timeout: int = 5,
) -> None:
    configure_logging()
    logger = logging.getLogger(name)

    init_db()
    logger.info("started; waiting for %s", queue_name)

    while True:
        task_id = wait_for_task(timeout)
        if task_id is None:
            continue

        db = SessionLocal()
        try:
            logger.info("processing task #%s", task_id)
            process_task(db, task_id)
        except Exception:
            logger.exception("task #%s failed outside handler", task_id)
            time.sleep(1)
        finally:
            db.close()
