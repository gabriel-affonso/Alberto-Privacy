from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.models.privacy_case import PrivacyCase
from app.response_analyzer.service import ingest_response

router = APIRouter(prefix="/cases", tags=["responses"])


@router.post("/{case_id}/responses")
async def upload_response(case_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if db.get(PrivacyCase, case_id) is None:
        raise HTTPException(404, "Case not found")
    content = await file.read(settings.privacy_max_upload_bytes + 1)
    try:
        files = ingest_response(db, case_id, file.filename or "response.bin", content, file.content_type, settings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"files": [{"id": item.id, "name": item.original_name, "sha256": item.sha256} for item in files]}
