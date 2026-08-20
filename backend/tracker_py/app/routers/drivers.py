from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.drivers import Driver
from app.schemas.drivers import DriverCreate, DriverOut, DriverUpdate

router = APIRouter(prefix="", tags=["drivers"])


@router.post("/drivers", response_model=DriverOut)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db)):
    driver = Driver(name=payload.name, rut=payload.rut, is_active=True, created_at=datetime.now(timezone.utc))
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


@router.get("/drivers", response_model=List[DriverOut])
def list_drivers(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(Driver)
    if not include_inactive:
        query = query.filter(Driver.is_active.is_(True))
    return query.order_by(Driver.id).all()


@router.patch("/drivers/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: int, payload: DriverUpdate, db: Session = Depends(get_db)):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Conductor no encontrado.")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        driver.name = data["name"].strip()
    if "rut" in data:
        driver.rut = data["rut"].strip() if data["rut"] else None
    if "is_active" in data and data["is_active"] is not None:
        driver.is_active = data["is_active"]

    db.commit()
    db.refresh(driver)
    return driver


@router.delete("/drivers/{driver_id}")
def delete_driver(driver_id: int, db: Session = Depends(get_db)):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Conductor no encontrado.")
    driver.is_active = False
    db.commit()
    return {"ok": True}
