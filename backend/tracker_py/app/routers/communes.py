from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.locations import Commune, Region
from app.schemas.locations import CommuneCreate, CommuneUpdate, CommuneOut

router = APIRouter(prefix="", tags=["communes"])


@router.post("/communes", response_model=CommuneOut)
def create_commune(payload: CommuneCreate, db: Session = Depends(get_db)):
    region = db.query(Region).filter(Region.id == payload.region_id).first()
    if not region:
        raise HTTPException(status_code=400, detail="region_id no existe.")

    commune = Commune(
        region_id=payload.region_id,
        name=payload.name.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(commune)
    db.commit()
    db.refresh(commune)
    return commune


@router.get("/communes", response_model=List[CommuneOut])
def list_communes(
    region_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Commune)
    if region_id is not None:
        q = q.filter(Commune.region_id == region_id)
    return q.order_by(Commune.id).all()


@router.get("/communes/{commune_id}", response_model=CommuneOut)
def get_commune(commune_id: int, db: Session = Depends(get_db)):
    commune = db.query(Commune).filter(Commune.id == commune_id).first()
    if not commune:
        raise HTTPException(status_code=404, detail="Comuna no encontrada.")
    return commune


@router.patch("/communes/{commune_id}", response_model=CommuneOut)
def update_commune(commune_id: int, payload: CommuneUpdate, db: Session = Depends(get_db)):
    commune = db.query(Commune).filter(Commune.id == commune_id).first()
    if not commune:
        raise HTTPException(status_code=404, detail="Comuna no encontrada.")

    data = payload.model_dump(exclude_unset=True)

    if "region_id" in data and data["region_id"] is not None:
        region = db.query(Region).filter(Region.id == data["region_id"]).first()
        if not region:
            raise HTTPException(status_code=400, detail="region_id no existe.")
        commune.region_id = data["region_id"]

    if "name" in data and data["name"] is not None:
        commune.name = data["name"].strip()

    db.commit()
    db.refresh(commune)
    return commune


@router.delete("/communes/{commune_id}")
def delete_commune(commune_id: int, db: Session = Depends(get_db)):
    commune = db.query(Commune).filter(Commune.id == commune_id).first()
    if not commune:
        raise HTTPException(status_code=404, detail="Comuna no encontrada.")

    db.delete(commune)
    db.commit()
    return {"ok": True}
