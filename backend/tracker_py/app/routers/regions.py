from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.locations import Region
from app.schemas.locations import RegionCreate, RegionUpdate, RegionOut

router = APIRouter(prefix="", tags=["regions"])


@router.post("/regions", response_model=RegionOut)
def create_region(payload: RegionCreate, db: Session = Depends(get_db)):
    region = Region(
        name=payload.name.strip(),
        code=(payload.code.strip() if payload.code else None),
        created_at=datetime.utcnow(),
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


@router.get("/regions", response_model=List[RegionOut])
def list_regions(db: Session = Depends(get_db)):
    return db.query(Region).order_by(Region.id).all()


@router.get("/regions/{region_id}", response_model=RegionOut)
def get_region(region_id: int, db: Session = Depends(get_db)):
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Región no encontrada.")
    return region


@router.patch("/regions/{region_id}", response_model=RegionOut)
def update_region(region_id: int, payload: RegionUpdate, db: Session = Depends(get_db)):
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Región no encontrada.")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        region.name = data["name"].strip()
    if "code" in data:
        region.code = data["code"].strip() if data["code"] else None

    db.commit()
    db.refresh(region)
    return region


@router.delete("/regions/{region_id}")
def delete_region(region_id: int, db: Session = Depends(get_db)):
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Región no encontrada.")

    db.delete(region)
    db.commit()
    return {"ok": True}
