from pydantic import BaseModel, Field
from typing import Literal, Optional

class CodeBaseRequest(BaseModel):
    path: str
    extensions: list[str]
    folders: list[str]
    files: list[str]

class CodeBase(BaseModel):
    name: str
    path: str
    type: Literal["file", "folder"]
    children: Optional[list['CodeBase']] = Field(default=None)
CodeBase.model_rebuild()

class CodeBaseResponse(BaseModel):
    codebase: CodeBase