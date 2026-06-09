from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Recipient


def list_recipients(db: Session) -> list[Recipient]:
    return list(db.scalars(select(Recipient).order_by(Recipient.email)).all())
