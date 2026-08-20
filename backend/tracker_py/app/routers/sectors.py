from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.locations import Sector, Fundo
from app.schemas.locations import SectorCreate, SectorUpdate, SectorOut

router = APIRouter(prefix="", tags=["sectors"])


@router.post("/sectors", response_model=SectorOut)
def create_sector(payload: SectorCreate, db: Session = Depends(get_db)):
    fundo = db.query(Fundo).filter(Fundo.id == payload.fundo_id).first()
    if not fundo:
        raise HTTPException(status_code=400, detail="fundo_id no existe.")

    sector = Sector(
        fundo_id=payload.fundo_id,
        name=payload.name.strip(),
        external_id=(payload.external_id.strip() if payload.external_id else None),
        sdp_code=(payload.sdp_code.strip() if payload.sdp_code else None),
        hectares_total=payload.hectares_total,
        created_at=datetime.utcnow(),
    )
    db.add(sector)
    db.commit()
    db.refresh(sector)
    return sector


@router.get("/sectors", response_model=List[SectorOut])
def list_sectors(
    fundo_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Sector)
    if fundo_id is not None:
        q = q.filter(Sector.fundo_id == fundo_id)
    return q.order_by(Sector.id).all()


@router.get("/sectors/{sector_id}", response_model=SectorOut)
def get_sector(sector_id: int, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector no encontrado.")
    return sector


@router.patch("/sectors/{sector_id}", response_model=SectorOut)
def update_sector(sector_id: int, payload: SectorUpdate, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector no encontrado.")

    data = payload.model_dump(exclude_unset=True)

    if "fundo_id" in data and data["fundo_id"] is not None:
        fundo = db.query(Fundo).filter(Fundo.id == data["fundo_id"]).first()
        if not fundo:
            raise HTTPException(status_code=400, detail="fundo_id no existe.")
        sector.fundo_id = data["fundo_id"]

    if "name" in data and data["name"] is not None:
        sector.name = data["name"].strip()

    if "external_id" in data:
        sector.external_id = data["external_id"].strip() if data["external_id"] else None

    if "sdp_code" in data:
        sector.sdp_code = data["sdp_code"].strip() if data["sdp_code"] else None

    if "hectares_total" in data:
        sector.hectares_total = data["hectares_total"]

    db.commit()
    db.refresh(sector)
    return sector


@router.delete("/sectors/{sector_id}")
def delete_sector(sector_id: int, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector no encontrado.")

    db.delete(sector)
    db.commit()
    return {"ok": True}
