from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.species import Species
from app.schemas.species import SpeciesCreate, SpeciesUpdate, SpeciesOut

router = APIRouter(prefix="", tags=["species"])


@router.post("/species", response_model=SpeciesOut)
def create_species(payload: SpeciesCreate, db: Session = Depends(get_db)):
    sp = Species(
        name=payload.name.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp


@router.get("/species", response_model=List[SpeciesOut])
def list_species(db: Session = Depends(get_db)):
    return db.query(Species).order_by(Species.id).all()


@router.get("/species/{species_id}", response_model=SpeciesOut)
def get_species(species_id: int, db: Session = Depends(get_db)):
    sp = db.query(Species).filter(Species.id == species_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Especie no encontrada.")
    return sp


@router.patch("/species/{species_id}", response_model=SpeciesOut)
def update_species(species_id: int, payload: SpeciesUpdate, db: Session = Depends(get_db)):
    sp = db.query(Species).filter(Species.id == species_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Especie no encontrada.")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        sp.name = data["name"].strip()

    db.commit()
    db.refresh(sp)
    return sp


@router.delete("/species/{species_id}")
def delete_species(species_id: int, db: Session = Depends(get_db)):
    sp = db.query(Species).filter(Species.id == species_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Especie no encontrada.")

    db.delete(sp)
    db.commit()
    return {"ok": True}
