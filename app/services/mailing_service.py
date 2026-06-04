from collections import Counter

from sqlalchemy.orm import Session

from app.models import EmailTask, Mailing, Recipient
from app.schemas import MailingCreate
from app.services.event_service import write_event
from app.services.notification_service import publish_notification
from app.services.queue_service import enqueue_email


def _counts_for_mailing(mailing: Mailing) -> Counter:
    return Counter(task.status for task in mailing.email_tasks)


def resolve_mailing_status(counts: Counter, total: int) -> str:
    if total == 0:
        return "failed"
    queued = counts["queued"]
    sending = counts["sending"]
    sent = counts["sent"]
    failed = counts["failed"]
    if sent == total:
        return "completed"
    if failed == total:
        return "failed"
    if queued or sending:
        return "processing"
    if sent and failed:
        return "partially_failed"
    return "created"


def update_mailing_status(db: Session, mailing: Mailing) -> str:

    counts = _counts_for_mailing(mailing)
    mailing.status = resolve_mailing_status(counts, len(mailing.email_tasks))
    db.commit()
    db.refresh(mailing)
    return mailing.status


def create_mailing(db: Session, payload: MailingCreate) -> Mailing:
    if payload.group:
        recipient_emails = [
            email
            for (email,) in db.query(Recipient.email)
            .filter(Recipient.group == payload.group)
            .order_by(Recipient.email)
            .all()
        ]
    else:
        recipient_emails = [str(email).lower() for email in payload.recipients or []]

    recipient_emails = sorted(set(recipient_emails))
    mailing = Mailing(title=payload.title, subject=payload.subject, body=payload.body, status="created")
    db.add(mailing)
    db.flush()

    queued_tasks: list[EmailTask] = []
    for recipient_email in recipient_emails:
        email_task = EmailTask(
            mailing_id=mailing.id,
            recipient_email=recipient_email,
            status="queued",
        )
        db.add(email_task)
        db.flush()
        queued_tasks.append(email_task)

    mailing.status = "processing" if recipient_emails else "failed"
    db.commit()
    db.refresh(mailing)

    for email_task in queued_tasks:
        enqueue_email(email_task.id)
        write_event(
            "email_queued",
            mailing_id=mailing.id,
            email_id=email_task.id,
            recipient=email_task.recipient_email,
        )

    write_event("mailing_created", mailing_id=mailing.id, total_recipients=len(recipient_emails))
    publish_notification(
        "mailing_created",
        mailing_id=mailing.id,
        total_recipients=len(recipient_emails),
        message="Рассылка создана",
    )
    return mailing


def mailing_to_summary(mailing: Mailing) -> dict:
    counts = _counts_for_mailing(mailing)
    total = len(mailing.email_tasks)
    status = resolve_mailing_status(counts, total)
    return {
        "id": mailing.id,
        "title": mailing.title,
        "subject": mailing.subject,
        "body": mailing.body,
        "status": status,
        "total_recipients": total,
        "queued_count": counts["queued"],
        "sending_count": counts["sending"],
        "sent_count": counts["sent"],
        "failed_count": counts["failed"],
    }


def retry_failed_emails(db: Session, mailing_id: int) -> int:
    failed_tasks = (
        db.query(EmailTask)
        .filter(EmailTask.mailing_id == mailing_id, EmailTask.status == "failed")
        .order_by(EmailTask.id)
        .all()
    )
    failed_task_ids = [task.id for task in failed_tasks]
    for task in failed_tasks:
        task.status = "queued"
        task.error = None
    mailing = db.get(Mailing, mailing_id)
    if mailing:
        mailing.status = "processing"
    db.commit()

    for task_id in failed_task_ids:
        enqueue_email(task_id)

    write_event("retry_failed_emails", mailing_id=mailing_id, count=len(failed_tasks))
    publish_notification(
        "retry_failed_emails",
        mailing_id=mailing_id,
        count=len(failed_tasks),
        message="Ошибочные письма возвращены в очередь",
    )
    return len(failed_tasks)
