from pathlib import Path
from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import (
    IMPORT_STATUS_DONE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_PROCESSING,
    IMPORT_STATUS_QUEUED,
)
from app.models import Recipient, RecipientImport, now_utc
from app.services.event_service import write_event
from app.services.notification_service import publish_notification
from app.services.queue_service import enqueue_import
from app.utils.file_parser import parse_recipients_file


def create_import_task(db: Session, file: UploadFile) -> RecipientImport:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("Загрузите файл .csv или .xlsx")

    target = Path(settings.upload_dir) / f"{uuid4().hex}{suffix}"
    with target.open("wb") as fh:
        while chunk := file.file.read(1024 * 1024):
            fh.write(chunk)

    import_task = RecipientImport(file_path=str(target), status=IMPORT_STATUS_QUEUED)
    db.add(import_task)
    db.commit()
    db.refresh(import_task)

    enqueue_import(import_task.id)
    write_event("import_queued", import_id=import_task.id)
    publish_notification("import_queued", import_id=import_task.id, message="Файл добавлен в очередь")
    return import_task


def _flush_batch(db: Session, batch: dict[str, dict]) -> int:
    # Resolve duplicates against only the emails in this batch, then insert the
    # rest. Avoids loading the entire recipients table into memory per import.
    if not batch:
        return 0
    existing = {
        email
        for (email,) in db.execute(
            select(Recipient.email).where(Recipient.email.in_(batch.keys()))
        ).all()
    }
    inserted = 0
    for email, fields in batch.items():
        if email in existing:
            continue
        db.add(Recipient(name=fields["name"], email=email, group=fields["group"]))
        inserted += 1
    db.commit()
    return inserted


def process_import_task(db: Session, import_id: int) -> RecipientImport | None:
    claim = db.execute(
        update(RecipientImport)
        .where(
            RecipientImport.id == import_id,
            RecipientImport.status.in_([IMPORT_STATUS_QUEUED, IMPORT_STATUS_PROCESSING]),
        )
        .values(status=IMPORT_STATUS_PROCESSING, attempts=RecipientImport.attempts + 1, error=None, updated_at=now_utc())
    )
    db.commit()
    if claim.rowcount == 0:
        return db.get(RecipientImport, import_id)

    import_task = db.get(RecipientImport, import_id)
    write_event("import_started", import_id=import_id)
    publish_notification("import_started", import_id=import_id, message="Импорт начался")

    seen: set[str] = set()
    total_rows = valid_emails = invalid_emails = duplicates = 0
    batch: dict[str, dict] = {}

    try:
        for row in parse_recipients_file(import_task.file_path):
            total_rows += 1
            raw_email = str(row.get("email", "")).strip().lower()
            name = str(row.get("name", "")).strip() or None
            group = str(row.get("group", "")).strip() or None

            try:
                normalized_email = validate_email(raw_email, check_deliverability=False).normalized.lower()
            except EmailNotValidError:
                invalid_emails += 1
                continue

            if normalized_email in seen:
                duplicates += 1
                continue

            seen.add(normalized_email)
            batch[normalized_email] = {"name": name, "group": group}

            if len(batch) >= settings.import_batch_size:
                inserted = _flush_batch(db, batch)
                valid_emails += inserted
                duplicates += len(batch) - inserted
                batch = {}

        inserted = _flush_batch(db, batch)
        valid_emails += inserted
        duplicates += len(batch) - inserted

        import_task = db.get(RecipientImport, import_id)
        import_task.total_rows = total_rows
        import_task.valid_emails = valid_emails
        import_task.invalid_emails = invalid_emails
        import_task.duplicates = duplicates
        import_task.status = IMPORT_STATUS_DONE
        db.commit()
        write_event(
            "import_completed",
            import_id=import_id,
            total_rows=total_rows,
            valid_emails=valid_emails,
            invalid_emails=invalid_emails,
            duplicates=duplicates,
        )
        publish_notification(
            "import_completed",
            import_id=import_id,
            message="Импорт завершен",
            total_rows=total_rows,
            valid_emails=valid_emails,
            invalid_emails=invalid_emails,
            duplicates=duplicates,
        )
    except Exception as exc:
        db.rollback()
        import_task = db.get(RecipientImport, import_id)
        import_task.status = IMPORT_STATUS_FAILED
        import_task.error = str(exc)
        db.commit()
        write_event("import_failed", import_id=import_id, error=str(exc))
        publish_notification("import_failed", import_id=import_id, message="Ошибка импорта", error=str(exc))

    db.refresh(import_task)
    return import_task
