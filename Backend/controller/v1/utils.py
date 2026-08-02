from controller.dependencies import get_db
from dtos.db import (
    CreateRecord,
    CreateRecordResponse,
    UpdateRecord,
    UpdateRecordResponse,
)
from dtos.utils import CodeBaseRequest, CodeBaseResponse
from fastapi import APIRouter, Depends
from utils.logger import get_logger
from utils.utils import _generate_codebase_tree

log = get_logger(__name__)
utils_router = APIRouter()

@utils_router.post("/utils/codebase", response_model=CodeBaseResponse)
async def get_codebase(req: CodeBaseRequest) -> CodeBaseResponse:
    log.info(f"Nhận request: {req}")
    return CodeBaseResponse(codebase=_generate_codebase_tree(**req.model_dump(), return_json=True).model_dump())


# Database endpoints
@utils_router.post("/database/create", response_model=CreateRecordResponse)
async def create_record(req: CreateRecord, db = Depends(get_db)):
    record_id = db.create(req.prompt, req.response)
    return CreateRecordResponse(id=record_id)

@utils_router.put("/database/update/{record_id}", response_model=UpdateRecordResponse)
async def update_record(record_id:str, req: UpdateRecord, db = Depends(get_db)):
    result = db.update(record_id=record_id, status=req.status, human_corrected=req.human_corrected)
    return UpdateRecordResponse(result=result)