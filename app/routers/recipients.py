from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import RecipientRead
from app.services.recipient_service import list_recipients

router = APIRouter(prefix="/recipients", tags=["recipients"])


@router.get("", response_model=list[RecipientRead])
def get_recipients(db: Session = Depends(get_db)):
    return list_recipients(db)
