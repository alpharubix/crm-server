from pymongo.synchronous.collection import Collection
from datetime import datetime
from starlette.responses import JSONResponse


def insert_notes(user_id,note,parent_id,collection: Collection):
    try:
        owner_id = user_id
        created_by_id = user_id
        modified_by_id = None
        notes = note
        parent_id = parent_id
        collection.insert_one({"owner_id":owner_id,"created_by_id":created_by_id,"modified_by_id":modified_by_id,"note":notes,"parent_id":parent_id,"created_time":datetime.now(),
        "modified_time":datetime.now()})
        return JSONResponse(status_code=201, content={'message':'Note saved successfully'})
    except Exception as e:
        print(e)

