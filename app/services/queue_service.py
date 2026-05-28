from app.redis_client import EMAIL_QUEUE, IMPORT_QUEUE, redis_client


def enqueue_import(import_id: int) -> None:
    redis_client.lpush(IMPORT_QUEUE, str(import_id))


def enqueue_email(email_task_id: int) -> None:
    redis_client.lpush(EMAIL_QUEUE, str(email_task_id))


def wait_for_import_task(timeout: int = 5) -> int | None:
    item = redis_client.brpop(IMPORT_QUEUE, timeout=timeout)
    return int(item[1]) if item else None


def wait_for_email_task(timeout: int = 5) -> int | None:
    item = redis_client.brpop(EMAIL_QUEUE, timeout=timeout)
    return int(item[1]) if item else None


def get_import_queue_size() -> int:
    return redis_client.llen(IMPORT_QUEUE)


def get_email_queue_size() -> int:
    return redis_client.llen(EMAIL_QUEUE)
