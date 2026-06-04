from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RecipientImport
from app.schemas import ImportCreateResponse, ImportRead
from app.services.import_service import create_import_task

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportCreateResponse)
def upload_import(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportCreateResponse:
    try:
        import_task = create_import_task(db, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ImportCreateResponse(
        import_id=import_task.id,
        status=import_task.status,
        message="Файл принят и добавлен в очередь на обработку",
    )


@router.get("/{import_id}", response_model=ImportRead)
def get_import(import_id: int, db: Session = Depends(get_db)) -> RecipientImport:
    import_task = db.get(RecipientImport, import_id)
    if import_task is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return import_task
