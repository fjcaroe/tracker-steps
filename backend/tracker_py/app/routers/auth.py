from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import create_access_token, get_current_user, get_user_cost_centers, verify_password
from app.models.users import User
from app.schemas.auth import LoginIn, TokenOut, UserOut
from app.schemas.cost_centers import CostCenterOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(User.username == payload.username)
        .filter(User.is_active == True)
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token({"sub": str(user.id), "username": user.username})
    ccs = get_user_cost_centers(db, user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
        "cost_centers": ccs,
    }


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current


@router.get("/me/cost_centers", response_model=List[CostCenterOut])
def my_cost_centers(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return get_user_cost_centers(db, current.id)
