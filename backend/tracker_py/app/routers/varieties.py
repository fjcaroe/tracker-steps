from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.species import Variety, Species
from app.schemas.species import VarietyCreate, VarietyUpdate, VarietyOut

router = APIRouter(prefix="", tags=["varieties"])


@router.post("/varieties", response_model=VarietyOut)
def create_variety(payload: VarietyCreate, db: Session = Depends(get_db)):
    sp = db.query(Species).filter(Species.id == payload.species_id).first()
    if not sp:
        raise HTTPException(status_code=400, detail="species_id no existe.")

    v = Variety(
        species_id=payload.species_id,
        name=payload.name.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.get("/varieties", response_model=List[VarietyOut])
def list_varieties(
    species_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Variety)
    if species_id is not None:
        q = q.filter(Variety.species_id == species_id)
    return q.order_by(Variety.id).all()


@router.get("/varieties/{variety_id}", response_model=VarietyOut)
def get_variety(variety_id: int, db: Session = Depends(get_db)):
    v = db.query(Variety).filter(Variety.id == variety_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variedad no encontrada.")
    return v


@router.patch("/varieties/{variety_id}", response_model=VarietyOut)
def update_variety(variety_id: int, payload: VarietyUpdate, db: Session = Depends(get_db)):
    v = db.query(Variety).filter(Variety.id == variety_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variedad no encontrada.")

    data = payload.model_dump(exclude_unset=True)

    if "species_id" in data and data["species_id"] is not None:
        sp = db.query(Species).filter(Species.id == data["species_id"]).first()
        if not sp:
            raise HTTPException(status_code=400, detail="species_id no existe.")
        v.species_id = data["species_id"]

    if "name" in data and data["name"] is not None:
        v.name = data["name"].strip()

    db.commit()
    db.refresh(v)
    return v


@router.delete("/varieties/{variety_id}")
def delete_variety(variety_id: int, db: Session = Depends(get_db)):
    v = db.query(Variety).filter(Variety.id == variety_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variedad no encontrada.")

    db.delete(v)
    db.commit()
    return {"ok": True}
