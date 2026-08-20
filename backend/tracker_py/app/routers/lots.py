from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.sessions import TrackingLot, TrackingSession
from app.schemas.lots import TrackingLotCreate, TrackingLotOut

router = APIRouter(prefix="", tags=["lots"])


@router.post("/lots", response_model=TrackingLotOut)
def create_lot(payload: TrackingLotCreate, db: Session = Depends(get_db)):
    session = db.query(TrackingSession).get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    lot = TrackingLot(
        name=payload.name,
        session_id=session.id,
        cost_center_id=session.cost_center_id,
        machine_id=session.machine_id,
        driver_id=session.driver_id,
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot


@router.get("/lots", response_model=List[TrackingLotOut])
def list_lots(db: Session = Depends(get_db)):
    return db.query(TrackingLot).order_by(TrackingLot.created_at.desc()).all()
