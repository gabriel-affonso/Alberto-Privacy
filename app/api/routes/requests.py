from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.crud.company import get_company
from app.db.deps import get_db
from app.gdpr_request_generator.service import approve_request, generate_request, update_draft
from app.models.gdpr_request import GdprRequest
from app.schemas.gdpr_request import GdprRequestRead, GdprRequestUpdate, RequestGenerate, SendEmailResult
from app.gmail_delivery import GmailSender, build_google_gmail_sender
from app.gmail_requests import send_approved_request
from app.gmail_discovery.client import build_google_gmail_client
from app.gmail_receive import sync_thread_responses

router = APIRouter(tags=["requests"])


def get_gmail_sender(settings: Settings = Depends(get_settings)) -> GmailSender:
    try:
        return build_google_gmail_sender(settings)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


def get_gmail_read_service(settings: Settings = Depends(get_settings)):
    try:
        return build_google_gmail_client(settings).service
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/companies/{company_id}/requests/generate", response_model=GdprRequestRead, status_code=201)
def generate_company_request(company_id: int, payload: RequestGenerate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> GdprRequest:
    company = get_company(db, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    try:
        return generate_request(db, company, settings, payload.request_type, payload.account_id, payload.include_advertising_modules)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/requests/{request_id}", response_model=GdprRequestRead)
def get_request(request_id: int, db: Session = Depends(get_db)) -> GdprRequest:
    request = db.get(GdprRequest, request_id)
    if request is None:
        raise HTTPException(404, "Request not found")
    return request


@router.patch("/requests/{request_id}", response_model=GdprRequestRead)
def patch_request(request_id: int, payload: GdprRequestUpdate, db: Session = Depends(get_db)) -> GdprRequest:
    request = db.get(GdprRequest, request_id)
    if request is None:
        raise HTTPException(404, "Request not found")
    try:
        return update_draft(db, request, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/requests/{request_id}/approve", response_model=GdprRequestRead)
def approve(request_id: int, db: Session = Depends(get_db)) -> GdprRequest:
    request = db.get(GdprRequest, request_id)
    if request is None:
        raise HTTPException(404, "Request not found")
    try:
        return approve_request(db, request)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/requests/{request_id}/send-email", response_model=SendEmailResult)
def send_email(request_id: int, db: Session = Depends(get_db), sender: GmailSender = Depends(get_gmail_sender), settings: Settings = Depends(get_settings)) -> SendEmailResult:
    request = db.get(GdprRequest, request_id)
    if request is None:
        raise HTTPException(404, "Request not found")
    try:
        communication = send_approved_request(db, request, sender, settings)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return SendEmailResult(request_id=request.id, communication_id=communication.id, gmail_message_id=communication.gmail_message_id or "", gmail_thread_id=communication.gmail_thread_id, status="SENT")


@router.post("/requests/{request_id}/sync-gmail")
def sync_gmail(request_id: int, db: Session = Depends(get_db), gmail_service=Depends(get_gmail_read_service), settings: Settings = Depends(get_settings)):
    request = db.get(GdprRequest, request_id)
    if request is None: raise HTTPException(404, "Request not found")
    try:
        return {"stored": sync_thread_responses(db, request, gmail_service, settings)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
