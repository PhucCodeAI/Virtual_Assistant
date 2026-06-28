from fastapi import APIRouter
from repositories.database import DataBase
from dtos.db import CreateRecordResponse, CreateRecord, UpdateRecordResponse, UpdateRecord


db = DataBase()
db_router = APIRouter()

@db_router.post("/database/create", response_model=CreateRecordResponse)
async def create_record(req: CreateRecord):
    record_id = db.create(req.prompt, req.response)
    return CreateRecordResponse(id=record_id)

@db_router.put("/database/update/{record_id}", response_model=UpdateRecordResponse)
async def update_record(record_id:str, req: UpdateRecord):
    result = db.update(record_id=record_id, status=req.status, human_corrected=req.human_corrected)
    return UpdateRecordResponse(result=result)