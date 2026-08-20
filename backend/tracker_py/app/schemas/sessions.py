import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from fastapi import Query

from app.models.enums import TrackingStatus

class SessionsDayOut(BaseModel):
    day: str
    points_count: int
    sessions_count: int
class SessionStart(BaseModel):
    machine_id: int
    driver_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    work_order_id: Optional[int] = None
    started_at: Optional[datetime] = None


class TrackingPointIn(BaseModel):
    timestamp: datetime = PydanticField(..., alias="ts")    
    lat: float
    lon: float
    speed_mps: Optional[float] = None
    accuracy_m: Optional[float] = None
    extra: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True)


class PointsBatchIn(BaseModel):
    points: List[TrackingPointIn]


class TrackingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: int
    driver_id: Optional[int]
    cost_center_id: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    status: TrackingStatus


class TrackingPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    lat: float
    lon: float
    speed_mps: Optional[float]
    accuracy_m: Optional[float]
    extra: Optional[dict]

class TrackPointOut(BaseModel):
    ts: datetime
    lat: float
    lon: float
    speed_mps: Optional[float] = None
    n: int = 1

class TrackResponse(BaseModel):
    items: List[TrackPointOut]
    next_cursor: Optional[str] = None
    resolution: str

class SessionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: int
    machine_name: Optional[str] = None
    driver_name: Optional[str] = None
    cost_center_name: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: TrackingStatus
    points_count: int

    work_order_id: Optional[int] = None
    labor_id: Optional[int] = None
    effort_factor: Optional[float] = None
    target_speed_kmh: Optional[float] = None

    total_distance_m: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    duration_hours: Optional[float] = None

    effective_hours: Optional[float] = None
    estimated_fuel_liters: Optional[float] = None
    last_point_ts: Optional[datetime] = None
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None
    last_speed_mps: Optional[float] = None
