from pydantic import BaseModel, ConfigDict


class LaborCreate(BaseModel):
    activity_id: int
    name: str
    code: str | None = None
    effort_factor: float | None = None
    target_speed_kmh: float | None = None


class LaborUpdate(BaseModel):
    activity_id: int | None = None
    name: str | None = None
    code: str | None = None
    effort_factor: float | None = None
    target_speed_kmh: float | None = None
    is_active: bool | None = None


class LaborOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_id: int
    name: str
    code: str | None

    effort_factor: float | None = None
    target_speed_kmh: float | None = None
    is_active: bool
