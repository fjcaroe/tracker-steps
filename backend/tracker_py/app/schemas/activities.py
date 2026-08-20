from pydantic import BaseModel, ConfigDict


class ActivityCreate(BaseModel):
    name: str
    code: str | None = None


class ActivityUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None
    is_active: bool
