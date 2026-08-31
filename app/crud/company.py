from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate


def create_company(db: Session, company_in: CompanyCreate) -> Company:
    company = Company(**company_in.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def get_company(db: Session, company_id: int) -> Company | None:
    return db.get(Company, company_id)


def list_companies(db: Session, skip: int = 0, limit: int = 100) -> list[Company]:
    return list(db.scalars(select(Company).offset(skip).limit(limit)).all())


def update_company(db: Session, company: Company, company_in: CompanyUpdate) -> Company:
    for field, value in company_in.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def delete_company(db: Session, company: Company) -> None:
    db.delete(company)
    db.commit()

