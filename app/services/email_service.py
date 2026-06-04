from datetime import datetime

from sqlalchemy.orm import Session

from app.models import EmailTask, Mailing
from app.services.event_service import write_event
from app.services.mailing_service import update_mailing_status
from app.services.notification_service import publish_notification
from app.utils.smtp_client import send_email


def process_email_task(db: Session, email_task_id: int) -> EmailTask:
    task = db.get(EmailTask, email_task_id)
    if task is None:
        raise ValueError(f"Email task {email_task_id} not found")

    mailing = db.get(Mailing, task.mailing_id)
    if mailing is None:
        raise ValueError(f"Mailing {task.mailing_id} not found")

    task.status = "sending"
    task.error = None
    db.commit()
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
        task.status = "sent"
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
        task.status = "failed"
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
