from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import (
    EMAIL_STATUS_FAILED,
    EMAIL_STATUS_QUEUED,
    EMAIL_STATUS_SENDING,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_PROCESSING,
    IMPORT_STATUS_QUEUED,
)
from app.models import EmailTask, Mailing, RecipientImport, now_utc
from app.services.event_service import write_event
from app.services.mailing_service import update_mailing_status
from app.services.notification_service import publish_notification


def fail_stale_import_tasks(db: Session) -> int:
    cutoff = now_utc() - timedelta(seconds=settings.watchdog_stale_seconds)
    stale_tasks = list(
        db.scalars(
            select(RecipientImport).where(
                RecipientImport.status.in_([IMPORT_STATUS_QUEUED, IMPORT_STATUS_PROCESSING]),
                RecipientImport.updated_at <= cutoff,
            )
        ).all()
    )
    if not stale_tasks:
        return 0

    error = f"Импорт не завершился за {settings.watchdog_stale_seconds} секунд"
    for import_task in stale_tasks:
        import_task.status = IMPORT_STATUS_FAILED
        import_task.error = error
    db.commit()

    for import_task in stale_tasks:
        write_event("import_failed", import_id=import_task.id, error=error)
        publish_notification("import_failed", import_id=import_task.id, message="Ошибка импорта", error=error)
    return len(stale_tasks)


def fail_stale_email_tasks(db: Session) -> int:
    cutoff = now_utc() - timedelta(seconds=settings.watchdog_stale_seconds)
    stale_tasks = (
        db.query(EmailTask)
        .filter(
            EmailTask.status.in_([EMAIL_STATUS_QUEUED, EMAIL_STATUS_SENDING]),
            EmailTask.updated_at <= cutoff,
        )
        .all()
    )
    if not stale_tasks:
        return 0

    mailing_ids = {task.mailing_id for task in stale_tasks}
    error = f"Отправка не завершилась за {settings.watchdog_stale_seconds} секунд"
    for task in stale_tasks:
        task.status = EMAIL_STATUS_FAILED
        task.error = error
    db.commit()

    for task in stale_tasks:
        write_event(
            "email_failed",
            mailing_id=task.mailing_id,
            email_id=task.id,
            recipient=task.recipient_email,
            error=error,
        )
        publish_notification(
            "email_failed",
            mailing_id=task.mailing_id,
            email_id=task.id,
            recipient=task.recipient_email,
            message="Ошибка отправки письма",
            error=error,
        )

    for mailing_id in mailing_ids:
        mailing = db.get(Mailing, mailing_id)
        if mailing is None:
            continue
        previous_status = mailing.status
        status = update_mailing_status(db, mailing)
        if status in {"completed", "partially_failed", "failed"} and status != previous_status:
            write_event("mailing_completed", mailing_id=mailing.id, status=status)
            publish_notification(
                "mailing_completed",
                mailing_id=mailing.id,
                status=status,
                message="Рассылка завершена",
            )
    return len(stale_tasks)


def run_watchdog_once(db: Session) -> dict[str, int]:
    return {
        "imports_failed": fail_stale_import_tasks(db),
        "emails_failed": fail_stale_email_tasks(db),
    }
