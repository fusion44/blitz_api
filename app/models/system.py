from typing import Optional

from pydantic import BaseModel
from pydantic.types import conint, constr


class LoginInput(BaseModel):
    password_a: constr(min_length=8)
    one_time_password: Optional[constr(
        min_length=6, max_length=6, regex="^[0-9]+$")] = None
