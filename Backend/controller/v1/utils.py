from fastapi import APIRouter
from utils.utils import _generate_codebase_tree
from utils.logger import get_logger
from dtos.utils import CodeBaseResponse, CodeBaseRequest
from repositories.database import DataBase
from dtos.db import CreateRecordResponse, CreateRecord, UpdateRecordResponse, UpdateRecord

log = get_logger(__name__)
utils_router = APIRouter()
db = DataBase()

# Codebase endpoints
@utils_router.post("/utils/codebase", response_model=CodeBaseResponse)
async def get_codebase(req: CodeBaseRequest) -> CodeBaseResponse:
    log.info(f"Nhận request: {req}")
    return CodeBaseResponse(codebase=_generate_codebase_tree(**req.model_dump(), return_json=True).model_dump())

# Database endpoints
@utils_router.post("/database/create", response_model=CreateRecordResponse)
async def create_record(req: CreateRecord):
    record_id = db.create(req.prompt, req.response)
    return CreateRecordResponse(id=record_id)

@utils_router.put("/database/update/{record_id}", response_model=UpdateRecordResponse)
async def update_record(record_id:str, req: UpdateRecord):
    result = db.update(record_id=record_id, status=req.status, human_corrected=req.human_corrected)
    return UpdateRecordResponse(result=result)