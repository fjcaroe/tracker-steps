from typing import List
from pydantic import BaseModel, ConfigDict

from app.schemas.cost_centers import CostCenterOut


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    is_admin: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
    cost_centers: List[CostCenterOut]
