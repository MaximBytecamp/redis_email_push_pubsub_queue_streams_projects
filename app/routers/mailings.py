from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import EmailTask, Mailing
from app.schemas import (
    EmailTaskRead,
    MailingCreate,
    MailingCreateResponse,
    MailingListItem,
    MailingRead,
)
from app.services.event_service import read_events
from app.services.mailing_service import create_mailing, mailing_to_summary, retry_failed_emails

router = APIRouter(prefix="/mailings", tags=["mailings"])


@router.post("", response_model=MailingCreateResponse)
def create_mailing_endpoint(payload: MailingCreate, db: Session = Depends(get_db)) -> MailingCreateResponse:
    mailing = create_mailing(db, payload)
    return MailingCreateResponse(
        mailing_id=mailing.id,
        status=mailing.status,
        total_recipients=len(mailing.email_tasks),
        message="Рассылка создана и письма добавлены в очередь",
    )


@router.get("", response_model=list[MailingListItem])
def list_mailings(db: Session = Depends(get_db)) -> list[dict]:
    mailings = (
        db.query(Mailing)
        .options(selectinload(Mailing.email_tasks))
        .order_by(Mailing.id.desc())
        .all()
    )
    return [mailing_to_summary(mailing) for mailing in mailings]


@router.get("/{mailing_id}", response_model=MailingRead)
def get_mailing(mailing_id: int, db: Session = Depends(get_db)) -> dict:
    mailing = (
        db.query(Mailing)
        .options(selectinload(Mailing.email_tasks))
        .filter(Mailing.id == mailing_id)
        .first()
    )
    if mailing is None:
        raise HTTPException(status_code=404, detail="Mailing not found")
    return mailing_to_summary(mailing)


@router.get("/{mailing_id}/emails", response_model=list[EmailTaskRead])
def get_mailing_emails(mailing_id: int, db: Session = Depends(get_db)) -> list[EmailTaskRead]:
    if db.get(Mailing, mailing_id) is None:
        raise HTTPException(status_code=404, detail="Mailing not found")
    tasks = (
        db.query(EmailTask)
        .filter(EmailTask.mailing_id == mailing_id)
        .order_by(EmailTask.id.desc())
        .all()
    )
    return [
        EmailTaskRead(id=task.id, recipient=task.recipient_email, status=task.status, error=task.error)
        for task in tasks
    ]


@router.post("/{mailing_id}/retry-failed")
def retry_failed(mailing_id: int, db: Session = Depends(get_db)) -> dict:
    if db.get(Mailing, mailing_id) is None:
        raise HTTPException(status_code=404, detail="Mailing not found")
    count = retry_failed_emails(db, mailing_id)
    return {"mailing_id": mailing_id, "requeued": count, "message": "Ошибочные письма возвращены в очередь"}


@router.get("/{mailing_id}/events")
def get_mailing_events(mailing_id: int, limit: int = 100) -> list[dict]:
    return read_events(limit=limit, mailing_id=mailing_id)
