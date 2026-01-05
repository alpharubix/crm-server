from fastapi import APIRouter, Depends, HTTPException
from pymongo.synchronous.collection import Collection
from starlette.requests import Request
from src.database import get_mongodb
from src.controllers.notes import insert_notes
from src.schemas.note import Note
notes_router = APIRouter(prefix='/notes')



@notes_router.post('/')
def create_notes( request:Request,body:Note,collection: Collection = Depends(get_mongodb)):
    return insert_notes(user_id=request.state.user_id, note=body.note,parent_id=body.id,collection=collection)












