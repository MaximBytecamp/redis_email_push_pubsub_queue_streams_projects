from app.redis_client import IMPORT_QUEUE
from app.services.import_service import process_import_task
from app.services.queue_service import wait_for_import_task
from app.workers.runner import run_worker


def main() -> None:
    run_worker(
        name="import_worker",
        queue_name=IMPORT_QUEUE,
        wait_for_task=wait_for_import_task,
        process_task=process_import_task,
    )


if __name__ == "__main__":
    main()
