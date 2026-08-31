from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.crud import account as account_crud
from app.crud.company import get_company
from app.db.deps import get_db
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(account_in: AccountCreate, db: Session = Depends(get_db)) -> AccountRead:
    if get_company(db, account_in.company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return account_crud.create_account(db, account_in)


@router.get("", response_model=list[AccountRead])
def list_accounts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> list[AccountRead]:
    return account_crud.list_accounts(db, skip=skip, limit=limit)


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: int, db: Session = Depends(get_db)) -> AccountRead:
    account = account_crud.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int, account_in: AccountUpdate, db: Session = Depends(get_db)
) -> AccountRead:
    account = account_crud.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account_in.company_id is not None and get_company(db, account_in.company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return account_crud.update_account(db, account, account_in)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db)) -> Response:
    account = account_crud.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    account_crud.delete_account(db, account)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

