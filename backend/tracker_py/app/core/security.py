from datetime import datetime, timedelta
from typing import List

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.cost_centers import CostCenter
from app.models.users import User, UserCostCenter


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict, expires_minutes: int = settings.JWT_EXPIRE_MIN) -> str:
    to_encode = dict(data)
    exp = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": exp})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token inválido")
        user_id = int(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(User).get(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user


def get_user_cost_centers(db: Session, user_id: int) -> List[CostCenter]:
    return (
        db.query(CostCenter)
        .join(UserCostCenter, UserCostCenter.cost_center_id == CostCenter.id)
        .filter(UserCostCenter.user_id == user_id)
        .order_by(CostCenter.name.asc())
        .all()
    )


def allowed_cost_center_ids(db: Session, user_id: int) -> list[int]:
    return [cc.id for cc in get_user_cost_centers(db, user_id)]


def assert_cost_center_access(db: Session, user: User, cost_center_id: int | None) -> None:
    """Impide que un usuario opere información fuera de sus centros asignados."""
    if user.is_admin:
        return
    if cost_center_id is None or cost_center_id not in set(allowed_cost_center_ids(db, user.id)):
        raise HTTPException(status_code=403, detail="Centro de costo no autorizado")


def require_admin_for_master_write(
    request: Request,
    current: User = Depends(get_current_user),
) -> User:
    """Permite consultar maestros a usuarios activos y limita su edición a administradores."""
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not current.is_admin:
        raise HTTPException(status_code=403, detail="Se requiere perfil administrador para modificar maestros")
    return current
