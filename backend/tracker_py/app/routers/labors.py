from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.activities import Labor, Activity
from app.schemas.labors import LaborCreate, LaborOut, LaborUpdate

router = APIRouter(prefix="", tags=["labors"])


@router.post("/labors", response_model=LaborOut)
def create_labor(payload: LaborCreate, db: Session = Depends(get_db)):
    activity = db.get(Activity, payload.activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    lab = Labor(
        activity_id=payload.activity_id,
        name=payload.name,
        code=payload.code,
        effort_factor=payload.effort_factor,
        target_speed_kmh=payload.target_speed_kmh,
    )
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


@router.get("/labors", response_model=List[LaborOut])
def list_labors(activity_id: int | None = None, include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(Labor)
    if not include_inactive:
        q = q.filter(Labor.is_active.is_(True))
    if activity_id is not None:
        q = q.filter(Labor.activity_id == activity_id)
    return q.order_by(Labor.name).all()


@router.put("/labors/{labor_id}", response_model=LaborOut)
def update_labor(labor_id: int, payload: LaborUpdate, db: Session = Depends(get_db)):
    labor = db.get(Labor, labor_id)
    if not labor:
        raise HTTPException(status_code=404, detail="Labor not found")

    data = payload.model_dump(exclude_unset=True)

    if "activity_id" in data and data["activity_id"] is not None:
        activity = db.get(Activity, data["activity_id"])
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

    for k, v in data.items():
        setattr(labor, k, v)

    db.commit()
    db.refresh(labor)
    return labor


@router.delete("/labors/{labor_id}")
def delete_labor(labor_id: int, db: Session = Depends(get_db)):
    labor = db.get(Labor, labor_id)
    if not labor:
        raise HTTPException(status_code=404, detail="Labor no encontrada.")
    labor.is_active = False
    db.commit()
    return {"ok": True}
