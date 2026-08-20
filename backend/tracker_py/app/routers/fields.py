from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.fields import Field
from app.models.cost_centers import CostCenter
from app.models.species import Species, Variety
from app.schemas.fields import FieldCreate, FieldOut, FieldUpdate

router = APIRouter(prefix="", tags=["fields"])


def _validate_polygon_or_400(polygon) -> None:
    if polygon is None:
        return
    if len(polygon) < 3:
        raise HTTPException(status_code=400, detail="El polígono debe tener al menos 3 puntos.")


def _resolve_cost_center_or_400(cost_center_id: Optional[int], db: Session) -> None:
    if cost_center_id is None:
        return
    cc = db.query(CostCenter).filter(CostCenter.id == cost_center_id).first()
    if not cc:
        raise HTTPException(status_code=400, detail="cost_center_id no existe.")


def _resolve_species_or_400(species_id: Optional[int], db: Session) -> Optional[Species]:
    if species_id is None:
        return None
    sp = db.query(Species).filter(Species.id == species_id).first()
    if not sp:
        raise HTTPException(status_code=400, detail="species_id no existe.")
    return sp


def _resolve_variety_or_400(variety_id: Optional[int], db: Session) -> Optional[Variety]:
    if variety_id is None:
        return None
    v = db.query(Variety).filter(Variety.id == variety_id).first()
    if not v:
        raise HTTPException(status_code=400, detail="variety_id no existe.")
    return v


def _validate_species_variety_consistency_or_400(
    species_id: Optional[int],
    variety: Optional[Variety],
) -> Optional[int]:
    """
    Retorna el species_id resultante:
    - Si viene variety y no viene species_id => usa variety.species_id
    - Si vienen ambos => valida pertenencia
    - Si no viene variety => deja species_id tal cual
    """
    if variety is None:
        return species_id

    if species_id is None:
        return variety.species_id

    if variety.species_id != species_id:
        raise HTTPException(
            status_code=400,
            detail="La variedad no pertenece a la especie indicada.",
        )
    return species_id


def _to_field_out(f: Field) -> FieldOut:
    return FieldOut(
        id=f.id,
        name=f.name,
        cost_center_id=f.cost_center_id,
        cost_center_name=f.cost_center.name if f.cost_center else None,
        color=f.color,
        polygon=f.polygon,
        created_at=f.created_at,
        species_id=f.species_id,
        species_name=f.species.name if f.species else None,
        variety_id=f.variety_id,
        variety_name=f.variety.name if f.variety else None,
    )


@router.post("/fields", response_model=FieldOut)
def create_field(payload: FieldCreate, db: Session = Depends(get_db)):
    _validate_polygon_or_400(payload.polygon)
    _resolve_cost_center_or_400(payload.cost_center_id, db)

    # Validación especie/variedad
    _resolve_species_or_400(payload.species_id, db)
    variety = _resolve_variety_or_400(payload.variety_id, db)
    final_species_id = _validate_species_variety_consistency_or_400(payload.species_id, variety)
    final_variety_id = variety.id if variety else None

    field = Field(
        name=payload.name,
        cost_center_id=payload.cost_center_id,
        color=payload.color,
        polygon=[p.model_dump() for p in payload.polygon],
        species_id=final_species_id,
        variety_id=final_variety_id,
    )

    db.add(field)
    db.commit()
    db.refresh(field)

    # Cargar relaciones para nombres
    field = (
        db.query(Field)
        .options(joinedload(Field.cost_center), joinedload(Field.species), joinedload(Field.variety))
        .filter(Field.id == field.id)
        .first()
    )

    return _to_field_out(field)


@router.get("/fields", response_model=List[FieldOut])
def list_fields(db: Session = Depends(get_db)):
    fields = (
        db.query(Field)
        .options(joinedload(Field.cost_center), joinedload(Field.species), joinedload(Field.variety))
        .order_by(Field.created_at.desc())
        .all()
    )
    return [_to_field_out(f) for f in fields]


@router.get("/fields/{field_id}", response_model=FieldOut)
def get_field(field_id: int, db: Session = Depends(get_db)):
    field = (
        db.query(Field)
        .options(joinedload(Field.cost_center), joinedload(Field.species), joinedload(Field.variety))
        .filter(Field.id == field_id)
        .first()
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return _to_field_out(field)


@router.put("/fields/{field_id}", response_model=FieldOut)
def update_field(field_id: int, payload: FieldUpdate, db: Session = Depends(get_db)):
    field = (
        db.query(Field)
        .options(joinedload(Field.cost_center), joinedload(Field.species), joinedload(Field.variety))
        .filter(Field.id == field_id)
        .first()
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    data = payload.model_dump(exclude_unset=True)

    # polygon (si viene)
    fields_set = payload.model_fields_set

    if "polygon" in fields_set:
        _validate_polygon_or_400(payload.polygon)
        if payload.polygon is not None:
            field.polygon = [p.model_dump() for p in payload.polygon]


    # cost_center_id (si viene)
    if "cost_center_id" in data:
        _resolve_cost_center_or_400(data["cost_center_id"], db)
        field.cost_center_id = data["cost_center_id"]

    # básicos
    if "name" in data and data["name"] is not None:
        field.name = data["name"]
    if "color" in data:
        field.color = data["color"]

    # especie/variedad (maneja null explícito)
    incoming_species_id = field.species_id
    incoming_variety_id = field.variety_id

    if "species_id" in data:
        # puede ser int o None (para limpiar)
        _resolve_species_or_400(data["species_id"], db)
        incoming_species_id = data["species_id"]

    variety_obj = None
    if "variety_id" in data:
        # puede ser int o None (para limpiar)
        variety_obj = _resolve_variety_or_400(data["variety_id"], db)
        incoming_variety_id = variety_obj.id if variety_obj else None
    else:
        # si no viene variety_id, pero tenemos uno actual y cambiaron species_id,
        # debemos validar consistencia con la variedad actual
        if "species_id" in data and field.variety_id is not None:
            variety_obj = _resolve_variety_or_400(field.variety_id, db)

    # Validación cruzada y auto-derivación species_id desde variedad si corresponde
    incoming_species_id = _validate_species_variety_consistency_or_400(incoming_species_id, variety_obj)

    # Asignación final
    if "species_id" in data or "variety_id" in data:
        field.species_id = incoming_species_id
        field.variety_id = incoming_variety_id

    db.commit()
    db.refresh(field)

    # refrescar relaciones
    field = (
        db.query(Field)
        .options(joinedload(Field.cost_center), joinedload(Field.species), joinedload(Field.variety))
        .filter(Field.id == field.id)
        .first()
    )

    return _to_field_out(field)


@router.delete("/fields/{field_id}")
def delete_field(field_id: int, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    db.delete(field)
    db.commit()
    return {"ok": True}
