from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.controller_resolver.resolver import ControllerResolver
from app.controller_resolver.service import resolve_controller_for_company
from app.core.config import Settings, get_settings
from app.crud import company as company_crud
from app.db.deps import get_db
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.schemas.controller_resolution import ControllerResolutionRead
from app.models.controller_resolution import ControllerResolution
from app.models.company import Company
from app.controller_resolver.types import ControllerResolutionResult

router = APIRouter(prefix="/companies", tags=["companies"])


def get_controller_resolver(settings: Settings = Depends(get_settings)) -> ControllerResolver:
    return ControllerResolver(
        max_pages=settings.controller_resolver_max_pages,
    )


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(company_in: CompanyCreate, db: Session = Depends(get_db)) -> CompanyRead:
    return company_crud.create_company(db, company_in)


@router.get("", response_model=list[CompanyRead])
def list_companies(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> list[CompanyRead]:
    return company_crud.list_companies(db, skip=skip, limit=limit)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: int, db: Session = Depends(get_db)) -> CompanyRead:
    company = company_crud.get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.post("/{company_id}/resolve-controller", response_model=ControllerResolutionRead)
def resolve_company_controller(
    company_id: int,
    db: Session = Depends(get_db),
    resolver: ControllerResolver = Depends(get_controller_resolver),
    settings: Settings = Depends(get_settings),
) -> ControllerResolutionRead:
    company = company_crud.get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    try:
        return resolve_controller_for_company(db, company, resolver, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{company_id}/controller", response_model=ControllerResolutionRead)
def get_company_controller(company_id: int, db: Session = Depends(get_db)) -> ControllerResolution:
    if company_crud.get_company(db, company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    resolution = db.scalars(
        select(ControllerResolution).where(ControllerResolution.company_id == company_id).order_by(ControllerResolution.queried_at.desc())
    ).first()
    if resolution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Controller has not been resolved")
    return resolution


@router.post("/resolve-pending", response_model=list[ControllerResolutionRead])
def resolve_pending_controllers(
    limit: int = 10, db: Session = Depends(get_db), resolver: ControllerResolver = Depends(get_controller_resolver), settings: Settings = Depends(get_settings)
) -> list[ControllerResolutionResult]:
    companies = list(db.scalars(select(Company).where(Company.last_resolved_at.is_(None)).limit(max(1, min(limit, 100)))).all())
    return [resolve_controller_for_company(db, company, resolver, settings) for company in companies if company.domain or company.website]


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: int, company_in: CompanyUpdate, db: Session = Depends(get_db)
) -> CompanyRead:
    company = company_crud.get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company_crud.update_company(db, company, company_in)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)) -> Response:
    company = company_crud.get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    company_crud.delete_company(db, company)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
