from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.privacy_case import PrivacyCase
from app.models.response_data import Identifier, ProvenanceEntity, ProvenanceRelation, ResponseFile

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.get("/entities")
def list_entities(db: Session = Depends(get_db)):
    return list(db.scalars(select(ProvenanceEntity)).all())


@router.get("/relations")
def list_relations(db: Session = Depends(get_db)):
    return list(db.scalars(select(ProvenanceRelation)).all())


@router.get("/company/{company_id}")
def company_provenance(company_id: int, db: Session = Depends(get_db)):
    # Relations are returned only when they have documentary evidence; no relationship is inferred here.
    return list(db.scalars(
        select(ProvenanceRelation).join(ResponseFile, ProvenanceRelation.response_file_id == ResponseFile.id)
        .join(PrivacyCase, ResponseFile.case_id == PrivacyCase.id).where(PrivacyCase.company_id == company_id)
    ).all())


@router.get("/identifier/{identifier_type}/{value_hash}")
def identifier_provenance(identifier_type: str, value_hash: str, db: Session = Depends(get_db)):
    return list(db.scalars(select(Identifier).where(Identifier.identifier_type == identifier_type, Identifier.value_hash == value_hash)).all())
