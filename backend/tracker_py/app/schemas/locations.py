from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# -------- Regions --------
class RegionCreate(BaseModel):
    name: str
    code: Optional[str] = None


class RegionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: Optional[str] = None


# -------- Communes --------
class CommuneCreate(BaseModel):
    region_id: int
    name: str


class CommuneUpdate(BaseModel):
    region_id: Optional[int] = None
    name: Optional[str] = None


class CommuneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    region_id: int
    name: str


# -------- Fundos --------
class FundoCreate(BaseModel):
    name: str
    external_id: Optional[str] = None
    commune_id: Optional[int] = None
    address: Optional[str] = None
    hectares_total: Optional[float] = None


class FundoUpdate(BaseModel):
    name: Optional[str] = None
    external_id: Optional[str] = None
    commune_id: Optional[int] = None
    address: Optional[str] = None
    hectares_total: Optional[float] = None


class FundoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    external_id: Optional[str] = None
    commune_id: Optional[int] = None
    address: Optional[str] = None
    hectares_total: Optional[float] = None


# -------- Sectors --------
class SectorCreate(BaseModel):
    fundo_id: int
    name: str
    external_id: Optional[str] = None
    sdp_code: Optional[str] = None
    hectares_total: Optional[float] = None


class SectorUpdate(BaseModel):
    fundo_id: Optional[int] = None
    name: Optional[str] = None
    external_id: Optional[str] = None
    sdp_code: Optional[str] = None
    hectares_total: Optional[float] = None


class SectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fundo_id: int
    name: str
    external_id: Optional[str] = None
    sdp_code: Optional[str] = None
    hectares_total: Optional[float] = None
