from app.redis_client import EMAIL_QUEUE
from app.services.email_service import process_email_task
from app.services.queue_service import wait_for_email_task
from app.workers.runner import run_worker


def main() -> None:
    run_worker(
        name="email_worker",
        queue_name=EMAIL_QUEUE,
        wait_for_task=wait_for_email_task,
        process_task=process_email_task,
    )


if __name__ == "__main__":
    main()
