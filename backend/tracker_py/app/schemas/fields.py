from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, constr


class LatLon(BaseModel):
    lat: float
    lon: float


class FieldCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    cost_center_id: Optional[int] = None
    color: Optional[str] = None
    polygon: List[LatLon]

    # NUEVO
    species_id: Optional[int] = None
    variety_id: Optional[int] = None


class FieldUpdate(BaseModel):
    name: Optional[constr(strip_whitespace=True, min_length=1)] = None
    cost_center_id: Optional[int] = None
    color: Optional[str] = None
    polygon: Optional[List[LatLon]] = None

    # NUEVO
    # Nota: si envías null explícito, se podrá limpiar gracias al router.
    species_id: Optional[int] = None
    variety_id: Optional[int] = None


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cost_center_id: Optional[int]
    cost_center_name: Optional[str]
    color: Optional[str]
    polygon: List[LatLon]
    created_at: datetime

    # NUEVO (útil para UI)
    species_id: Optional[int]
    species_name: Optional[str]
    variety_id: Optional[int]
    variety_name: Optional[str]
