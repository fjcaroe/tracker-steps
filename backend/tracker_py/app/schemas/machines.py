from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, model_validator


FuelUnit = Literal["lph", "kmpl"]


def _validate_unit_consistency(
    unit: FuelUnit | None,
    lph: float | None,
    kmpl: float | None,
) -> None:
    u: FuelUnit = unit or "lph"

    # No permitir ambos al mismo tiempo
    if lph is not None and kmpl is not None:
        raise ValueError("No puedes enviar fuel_consumption_lph y fuel_efficiency_kmpl a la vez.")

    if u == "lph":
        # si la unidad es L/h, km/L debe ser null
        if kmpl is not None:
            raise ValueError("Si fuel_consumption_unit='lph', fuel_efficiency_kmpl debe ser null.")
    else:  # kmpl
        # si la unidad es km/L, L/h debe ser null
        if lph is not None:
            raise ValueError("Si fuel_consumption_unit='kmpl', fuel_consumption_lph debe ser null.")


class MachineCreate(BaseModel):
    external_id: str | None = None
    name: str
    plate: str | None = None
    description: str | None = None
    cost_center_id: int | None = None
    tank_capacity_liters: float | None = None

    # NUEVO
    fuel_consumption_unit: FuelUnit = "lph"   # 'lph' o 'kmpl'
    fuel_consumption_lph: float | None = None
    fuel_efficiency_kmpl: float | None = None

    # LEGACY (idealmente dejar de usar en front)
    fuel_consumption_lpkm: float | None = None

    default_activity_id: int | None = None
    default_labor_id: int | None = None

    @model_validator(mode="after")
    def _check(self):
        _validate_unit_consistency(
            self.fuel_consumption_unit,
            self.fuel_consumption_lph,
            self.fuel_efficiency_kmpl,
        )
        return self


class MachineUpdate(BaseModel):
    external_id: str | None = None
    name: str | None = None
    plate: str | None = None
    description: str | None = None
    cost_center_id: int | None = None
    tank_capacity_liters: float | None = None

    # NUEVO
    fuel_consumption_unit: FuelUnit | None = None
    fuel_consumption_lph: float | None = None
    fuel_efficiency_kmpl: float | None = None

    # LEGACY
    fuel_consumption_lpkm: float | None = None

    default_activity_id: int | None = None
    default_labor_id: int | None = None

    @model_validator(mode="after")
    def _check(self):
        # En update permitimos payload parcial, pero si vienen campos de consumo
        # validamos consistencia local del payload (no contra DB).
        _validate_unit_consistency(
            self.fuel_consumption_unit,
            self.fuel_consumption_lph,
            self.fuel_efficiency_kmpl,
        )
        return self


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None = None
    name: str
    plate: str | None = None
    description: str | None = None
    cost_center_id: int | None = None
    tank_capacity_liters: float | None = None

    # NUEVO
    fuel_consumption_unit: FuelUnit | None = None
    fuel_consumption_lph: float | None = None
    fuel_efficiency_kmpl: float | None = None

    # LEGACY
    fuel_consumption_lpkm: float | None = None

    default_activity_id: int | None = None
    default_labor_id: int | None = None


class FuelStatusOut(BaseModel):
    machine_id: int
    tank_capacity_liters: float | None = None
    last_liters: float | None = None
    last_work_order_id: int | None = None
    as_of: Optional[str] = None


class MachineOdometerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_distance_m: float
    total_sessions: int
    last_session_at: Optional[str] = None
