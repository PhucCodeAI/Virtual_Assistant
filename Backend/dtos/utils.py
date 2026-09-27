from typing import Literal

from pydantic import BaseModel, Field


class CodeBase(BaseModel):
    name: str
    path: str
    type: Literal["file", "folder"]
    children: list['CodeBase'] = Field(default=None)