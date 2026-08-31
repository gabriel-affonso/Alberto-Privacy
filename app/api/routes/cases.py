from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.case_manager.service import transition_case
from app.db.deps import get_db
from app.models.privacy_case import PrivacyCase
from app.response_analyzer.report import case_report
from app.schemas.privacy_case import CaseRead, CaseTransition

router = APIRouter(prefix="/cases", tags=["cases"])


def _case_query():
    return select(PrivacyCase).options(selectinload(PrivacyCase.events))


@router.get("", response_model=list[CaseRead])
def list_cases(db: Session = Depends(get_db)) -> list[PrivacyCase]:
    return list(db.scalars(_case_query().order_by(PrivacyCase.created_at.desc())).all())


@router.get("/overdue", response_model=list[CaseRead])
def overdue_cases(db: Session = Depends(get_db)) -> list[PrivacyCase]:
    today = date.today()
    return list(db.scalars(_case_query().where(PrivacyCase.deadline < today, PrivacyCase.status.not_in(["COMPLETED", "CANCELLED", "REJECTED"]))).all())


@router.get("/pending-action", response_model=list[CaseRead])
def pending_action_cases(db: Session = Depends(get_db)) -> list[PrivacyCase]:
    return list(db.scalars(_case_query().where(PrivacyCase.status.in_(["NEEDS_IDENTITY_VERIFICATION", "NEEDS_USER_ACTION", "WAITING_FOR_APPROVAL"]))).all())


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: int, db: Session = Depends(get_db)) -> PrivacyCase:
    case = db.scalar(_case_query().where(PrivacyCase.id == case_id))
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


@router.post("/{case_id}/transition", response_model=CaseRead)
def change_case_status(case_id: int, payload: CaseTransition, db: Session = Depends(get_db)) -> PrivacyCase:
    case = db.scalar(_case_query().where(PrivacyCase.id == case_id))
    if case is None:
        raise HTTPException(404, "Case not found")
    try:
        return transition_case(db, case, payload.status, payload.note, payload.extension_deadline)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{case_id}/report")
def get_case_report(case_id: int, db: Session = Depends(get_db)):
    if db.get(PrivacyCase, case_id) is None:
        raise HTTPException(404, "Case not found")
    return case_report(db, case_id)
