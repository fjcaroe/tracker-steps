from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.implements import Implement
from app.schemas.implements import ImplementCreate, ImplementOut, ImplementUpdate

router = APIRouter(prefix="", tags=["implements"])


@router.post("/implements", response_model=ImplementOut)
def create_implement(payload: ImplementCreate, db: Session = Depends(get_db)):
    exists = db.query(Implement).filter(func.lower(Implement.name) == payload.name.lower()).first()
    if exists:
        if not exists.is_active:
            exists.is_active = True
            db.commit()
            db.refresh(exists)
        return exists

    imp = Implement(name=payload.name)
    db.add(imp)
    db.commit()
    db.refresh(imp)
    return imp


@router.get("/implements", response_model=List[ImplementOut])
def list_implements(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(Implement)
    if not include_inactive:
        query = query.filter(Implement.is_active.is_(True))
    return query.order_by(Implement.name.asc()).all()


@router.patch("/implements/{implement_id}", response_model=ImplementOut)
def update_implement(implement_id: int, payload: ImplementUpdate, db: Session = Depends(get_db)):
    implement = db.get(Implement, implement_id)
    if not implement:
        raise HTTPException(status_code=404, detail="Implemento no encontrado.")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        duplicate = db.query(Implement).filter(
            Implement.id != implement_id,
            func.lower(Implement.name) == data["name"].lower(),
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Ya existe un implemento con ese nombre.")
        implement.name = data["name"]
    if "is_active" in data and data["is_active"] is not None:
        implement.is_active = data["is_active"]

    db.commit()
    db.refresh(implement)
    return implement


@router.delete("/implements/{implement_id}")
def delete_implement(implement_id: int, db: Session = Depends(get_db)):
    implement = db.get(Implement, implement_id)
    if not implement:
        raise HTTPException(status_code=404, detail="Implemento no encontrado.")
    implement.is_active = False
    db.commit()
    return {"ok": True}
