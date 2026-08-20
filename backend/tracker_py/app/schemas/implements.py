from datetime import datetime
from pydantic import BaseModel, ConfigDict, constr


class ImplementCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)


class ImplementUpdate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1) | None = None
    is_active: bool | None = None


class ImplementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    is_active: bool
