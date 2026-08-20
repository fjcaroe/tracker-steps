from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# -------- Species --------
class SpeciesCreate(BaseModel):
    name: str


class SpeciesUpdate(BaseModel):
    name: Optional[str] = None


class SpeciesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# -------- Varieties --------
class VarietyCreate(BaseModel):
    species_id: int
    name: str


class VarietyUpdate(BaseModel):
    species_id: Optional[int] = None
    name: Optional[str] = None


class VarietyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    species_id: int
    name: str
