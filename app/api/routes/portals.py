from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.case_manager.service import transition_case
from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.models.privacy_case import PrivacyCase
from app.privacy_portals import GenericPrivacyPortal

router = APIRouter(prefix="/cases", tags=["privacy portals"])


@router.post("/{case_id}/portal/prepare")
def prepare_portal(case_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    case = db.get(PrivacyCase, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    request = case.gdpr_request
    url = request.company.privacy_request_url
    if not url:
        raise HTTPException(422, "No verified privacy request URL is available")
    portal = GenericPrivacyPortal(url, Path(settings.privacy_data_root) / str(case.id) / "evidence")
    try:
        portal.open()
        portal.navigate_to_request()
        portal.fill_request(request.subject or "", request.body_text or "")
        preview = portal.review()
        if case.status == "APPROVED":
            transition_case(db, case, "WAITING_FOR_APPROVAL", "Portal request prepared; explicit approval required")
        return {"url": preview.url, "captured_at": preview.captured_at, "status": "WAITING_FOR_APPROVAL"}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
