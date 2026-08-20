from datetime import date
from pydantic import BaseModel, ConfigDict


class WorkOrderCreate(BaseModel):
    code: str
    work_date: date
    season: str
    machine_id: int
    activity_id: int
    labor_id: int
    cost_center_id: int | None = None
    field_id: int | None = None
    notes: str | None = None

    implement_id: int | None = None
    hourmeter_initial: float | None = None
    hourmeter_final: float | None = None
    fuel_tank_start_liters: float | None = None
    fuel_refill_liters: float | None = None
    fuel_tank_end_liters: float | None = None


class WorkOrderUpdate(BaseModel):
    implement_id: int | None = None
    hourmeter_initial: float | None = None
    hourmeter_final: float | None = None
    fuel_tank_start_liters: float | None = None
    fuel_refill_liters: float | None = None
    fuel_tank_end_liters: float | None = None
    notes: str | None = None


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    work_date: date
    season: str
    machine_id: int
    activity_id: int
    labor_id: int
    cost_center_id: int | None
    field_id: int | None
    notes: str | None

    implement_id: int | None = None
    hourmeter_initial: float | None = None
    hourmeter_final: float | None = None
    fuel_tank_start_liters: float | None = None
    fuel_refill_liters: float | None = None
    fuel_tank_end_liters: float | None = None
