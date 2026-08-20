from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.activities import Activity
from app.schemas.activities import ActivityCreate, ActivityOut, ActivityUpdate

router = APIRouter(prefix="", tags=["activities"])


@router.post("/activities", response_model=ActivityOut)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    act = Activity(name=payload.name, code=payload.code)
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


@router.get("/activities", response_model=List[ActivityOut])
def list_activities(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(Activity)
    if not include_inactive:
        query = query.filter(Activity.is_active.is_(True))
    return query.order_by(Activity.name).all()


@router.put("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(activity_id: int, payload: ActivityUpdate, db: Session = Depends(get_db)):
    act = db.get(Activity, activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(act, k, v)

    db.commit()
    db.refresh(act)
    return act


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada.")
    activity.is_active = False
    db.commit()
    return {"ok": True}
