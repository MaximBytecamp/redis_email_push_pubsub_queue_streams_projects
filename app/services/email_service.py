from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.constants import EMAIL_STATUS_FAILED, EMAIL_STATUS_QUEUED, EMAIL_STATUS_SENDING, EMAIL_STATUS_SENT
from app.models import EmailTask, Mailing, now_utc
from app.services.event_service import write_event
from app.services.mailing_service import update_mailing_status
from app.services.notification_service import publish_notification
from app.utils.smtp_client import send_email


def process_email_task(db: Session, email_task_id: int) -> EmailTask:
    claim = db.execute(
        update(EmailTask)
        .where(EmailTask.id == email_task_id, EmailTask.status == EMAIL_STATUS_QUEUED)
        .values(status=EMAIL_STATUS_SENDING, error=None, updated_at=now_utc())
    )
    db.commit()
    task = db.get(EmailTask, email_task_id)
    if task is None:
        raise ValueError(f"Email task {email_task_id} not found")
    if claim.rowcount == 0:
        return task

    mailing = db.get(Mailing, task.mailing_id)
    if mailing is None:
        raise ValueError(f"Mailing {task.mailing_id} not found")

    write_event("email_sending", mailing_id=mailing.id, email_id=task.id, recipient=task.recipient_email)
    publish_notification(
        "email_sending",
        mailing_id=mailing.id,
        email_id=task.id,
        recipient=task.recipient_email,
        message="Письмо отправляется",
    )

    try:
        send_email(task.recipient_email, mailing.subject, mailing.body)
        db.refresh(task)
        if task.status == EMAIL_STATUS_FAILED:
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
            return task

        task.status = EMAIL_STATUS_SENT
        task.sent_at = datetime.utcnow()
        task.error = None
        db.commit()
        write_event("email_sent", mailing_id=mailing.id, email_id=task.id, recipient=task.recipient_email)
        publish_notification(
            "email_sent",
            mailing_id=mailing.id,
            email_id=task.id,
            recipient=task.recipient_email,
            message="Письмо успешно отправлено",
        )
    except Exception as exc:
        task.status = EMAIL_STATUS_FAILED
        task.error = str(exc)
        db.commit()
        write_event(
            "email_failed",
            mailing_id=mailing.id,
            email_id=task.id,
            recipient=task.recipient_email,
            error=str(exc),
        )
        publish_notification(
            "email_failed",
            mailing_id=mailing.id,
            email_id=task.id,
            recipient=task.recipient_email,
            message="Ошибка отправки письма",
            error=str(exc),
        )

    db.refresh(mailing)
    previous_status = mailing.status
    status = update_mailing_status(db, mailing)
    if status in {"completed", "partially_failed", "failed"} and status != previous_status:
        write_event("mailing_completed", mailing_id=mailing.id, status=status)
        publish_notification("mailing_completed", mailing_id=mailing.id, status=status, message="Рассылка завершена")

    db.refresh(task)
    return task
