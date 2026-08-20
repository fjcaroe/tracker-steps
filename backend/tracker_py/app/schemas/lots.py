from datetime import datetime
from typing import Optional
from uuid import UUID as UUID_t
from pydantic import BaseModel, ConfigDict, constr


class TrackingLotCreate(BaseModel):
    session_id: UUID_t
    name: constr(strip_whitespace=True, min_length=1)


class TrackingLotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID_t
    name: str
    session_id: UUID_t
    cost_center_id: Optional[int]
    machine_id: Optional[int]
    driver_id: Optional[int]
    created_at: datetime
