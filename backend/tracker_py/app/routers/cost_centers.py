from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.session import get_db
from app.models.cost_centers import CostCenter
from app.models.species import Variety
from app.schemas.cost_centers import CostCenterCreate, CostCenterUpdate, CostCenterOut

router = APIRouter(prefix="", tags=["cost_centers"])


def _load_cost_center_or_404(cost_center_id: int, db: Session) -> CostCenter:
    cc = (
        db.query(CostCenter)
        .options(
            joinedload(CostCenter.sector),
            selectinload(CostCenter.varieties),
        )
        .filter(CostCenter.id == cost_center_id)
        .first()
    )
    if not cc:
        raise HTTPException(status_code=404, detail="Centro de costo no encontrado.")
    return cc


def _resolve_varieties_or_400(variety_ids: List[int], db: Session) -> List[Variety]:
    # elimina duplicados sin perder la intención (DB no necesita repetidos)
    unique_ids = list(dict.fromkeys(variety_ids))

    varieties = db.query(Variety).filter(Variety.id.in_(unique_ids)).all()
    if len(varieties) != len(unique_ids):
        raise HTTPException(status_code=400, detail="Una o más variedades no existen.")
    return varieties


@router.post("/cost_centers", response_model=CostCenterOut)
def create_cost_center(payload: CostCenterCreate, db: Session = Depends(get_db)):
    cc = CostCenter(
        name=payload.name.strip(),
        external_id=payload.external_id.strip() if payload.external_id else None,
        hectares=payload.hectares,
        sector_id=payload.sector_id,
        row_count=payload.row_count,
        plant_count=payload.plant_count,
        species_id=payload.species_id,
        created_at=datetime.utcnow(),
    )

    # Variedades (multi)
    if payload.variety_ids:
        cc.varieties = _resolve_varieties_or_400(payload.variety_ids, db)

    db.add(cc)
    db.commit()
    db.refresh(cc)
    return cc


@router.get("/cost_centers", response_model=List[CostCenterOut])
def list_cost_centers(db: Session = Depends(get_db)):
    return (
        db.query(CostCenter)
        .options(
            joinedload(CostCenter.sector),
            selectinload(CostCenter.varieties),
        )
        .order_by(CostCenter.id)
        .all()
    )


@router.get("/cost_centers/{cost_center_id}", response_model=CostCenterOut)
def get_cost_center(cost_center_id: int, db: Session = Depends(get_db)):
    return _load_cost_center_or_404(cost_center_id, db)


@router.patch("/cost_centers/{cost_center_id}", response_model=CostCenterOut)
def update_cost_center(cost_center_id: int, payload: CostCenterUpdate, db: Session = Depends(get_db)):
    cc = _load_cost_center_or_404(cost_center_id, db)
    data = payload.model_dump(exclude_unset=True)

    # Campos simples
    if "name" in data and data["name"] is not None:
        cc.name = data["name"].strip()

    if "external_id" in data:
        cc.external_id = data["external_id"].strip() if data["external_id"] else None

    if "hectares" in data:
        cc.hectares = data["hectares"]

    if "sector_id" in data:
        cc.sector_id = data["sector_id"]

    if "row_count" in data:
        cc.row_count = data["row_count"]

    if "plant_count" in data:
        cc.plant_count = data["plant_count"]

    if "species_id" in data:
        cc.species_id = data["species_id"]

    # Variedades:
    # - si viene variety_ids: se setea explícitamente (incluye vaciar si viene [])
    # - si NO viene: no se toca
    if "variety_ids" in data:
        variety_ids = data["variety_ids"]
        if variety_ids is None:
            # explícitamente null => lo tratamos como "no tocar" (opcional)
            # si prefieres que null signifique vaciar, cambia por: cc.varieties = []
            pass
        elif len(variety_ids) == 0:
            cc.varieties = []
        else:
            cc.varieties = _resolve_varieties_or_400(variety_ids, db)

    db.commit()
    db.refresh(cc)
    return cc


@router.delete("/cost_centers/{cost_center_id}")
def delete_cost_center(cost_center_id: int, db: Session = Depends(get_db)):
    cc = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Centro de costo no encontrado.")

    db.delete(cc)
    db.commit()
    return {"ok": True}
