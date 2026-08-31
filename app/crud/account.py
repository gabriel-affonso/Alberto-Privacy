from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


def create_account(db: Session, account_in: AccountCreate) -> Account:
    account = Account(**account_in.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_account(db: Session, account_id: int) -> Account | None:
    return db.get(Account, account_id)


def list_accounts(db: Session, skip: int = 0, limit: int = 100) -> list[Account]:
    return list(db.scalars(select(Account).offset(skip).limit(limit)).all())


def update_account(db: Session, account: Account, account_in: AccountUpdate) -> Account:
    for field, value in account_in.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account: Account) -> None:
    db.delete(account)
    db.commit()

