from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class VarietyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    species_id: int

class SectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sdp_code: Optional[str] = None
    fundo_id: int

class CostCenterCreate(BaseModel):
    name: str
    external_id: Optional[str] = None
    hectares: Optional[float] = None

    sector_id: Optional[int] = None
    row_count: Optional[int] = None
    plant_count: Optional[int] = None

    species_id: Optional[int] = None
    variety_ids: Optional[List[int]] = None

class CostCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    external_id: Optional[str] = None
    hectares: Optional[float] = None

    sector: Optional[SectorOut] = None
    row_count: Optional[int] = None
    plant_count: Optional[int] = None

    species_id: Optional[int] = None
    varieties: List[VarietyOut] = []


class CostCenterUpdate(BaseModel):
    name: Optional[str] = None
    external_id: Optional[str] = None
    hectares: Optional[float] = None

    sector_id: Optional[int] = None
    row_count: Optional[int] = None
    plant_count: Optional[int] = None

    species_id: Optional[int] = None

    variety_ids: Optional[List[int]] = None