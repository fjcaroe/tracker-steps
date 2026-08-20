from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.locations import Fundo, Commune
from app.schemas.locations import FundoCreate, FundoUpdate, FundoOut

router = APIRouter(prefix="", tags=["fundos"])

from sqlalchemy.exc import IntegrityError, ProgrammingError
from psycopg2.errors import UniqueViolation

@router.post("/fundos", response_model=FundoOut)
def create_fundo(payload: FundoCreate, db: Session = Depends(get_db)):
    if payload.commune_id is not None:
        commune = db.query(Commune).filter(Commune.id == payload.commune_id).first()
        if not commune:
            raise HTTPException(status_code=400, detail="commune_id no existe.")

    fundo = Fundo(
        name=payload.name.strip(),
        external_id=(payload.external_id.strip() if payload.external_id else None),
        commune_id=payload.commune_id,
        address=(payload.address.strip() if payload.address else None),
        hectares_total=payload.hectares_total,
        created_at=datetime.utcnow(),
    )

    try:
        db.add(fundo)
        db.commit()
        db.refresh(fundo)
        return fundo
    except IntegrityError as e:
        db.rollback()
        # nombre duplicado u otras constraints
        raise HTTPException(status_code=409, detail="Ya existe un fundo con ese nombre.")
    except ProgrammingError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error de permisos o configuración de base de datos.")


@router.get("/fundos", response_model=List[FundoOut])
def list_fundos(
    commune_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Fundo)
    if commune_id is not None:
        q = q.filter(Fundo.commune_id == commune_id)
    return q.order_by(Fundo.id).all()


@router.get("/fundos/{fundo_id}", response_model=FundoOut)
def get_fundo(fundo_id: int, db: Session = Depends(get_db)):
    fundo = db.query(Fundo).filter(Fundo.id == fundo_id).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo no encontrado.")
    return fundo


@router.patch("/fundos/{fundo_id}", response_model=FundoOut)
def update_fundo(fundo_id: int, payload: FundoUpdate, db: Session = Depends(get_db)):
    fundo = db.query(Fundo).filter(Fundo.id == fundo_id).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo no encontrado.")

    data = payload.model_dump(exclude_unset=True)

    if "commune_id" in data:
        if data["commune_id"] is not None:
            commune = db.query(Commune).filter(Commune.id == data["commune_id"]).first()
            if not commune:
                raise HTTPException(status_code=400, detail="commune_id no existe.")
        fundo.commune_id = data["commune_id"]

    if "name" in data and data["name"] is not None:
        fundo.name = data["name"].strip()

    if "external_id" in data:
        fundo.external_id = data["external_id"].strip() if data["external_id"] else None

    if "address" in data:
        fundo.address = data["address"].strip() if data["address"] else None

    if "hectares_total" in data:
        fundo.hectares_total = data["hectares_total"]

    db.commit()
    db.refresh(fundo)
    return fundo


@router.delete("/fundos/{fundo_id}")
def delete_fundo(fundo_id: int, db: Session = Depends(get_db)):
    fundo = db.query(Fundo).filter(Fundo.id == fundo_id).first()
    if not fundo:
        raise HTTPException(status_code=404, detail="Fundo no encontrado.")

    db.delete(fundo)
    db.commit()
    return {"ok": True}
