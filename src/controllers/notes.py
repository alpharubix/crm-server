from datetime import datetime
from fastapi.exceptions import HTTPException
from pymongo.synchronous.collection import Collection
from starlette.responses import JSONResponse


def insert_notes(user_id, note, parent_id, collection: Collection):
    try:
        owner_id = user_id
        created_by_id = user_id
        modified_by_id = None
        notes = note
        parent_id = parent_id
        collection.insert_one(
            {
                "owner_id": owner_id,
                "created_by_id": created_by_id,
                "modified_by_id": modified_by_id,
                "note": notes,
                "parent_id": parent_id,
                "created_time": datetime.now(),
                "modified_time": datetime.now(),
            }
        )
        return JSONResponse(
            status_code=201, content={"message": "Note saved successfully"}
        )
    except Exception as e:
        print(e)


def get_notes(acc_ids: list, live_notes_collection: Collection):
    try:
        notes_cursor = live_notes_collection.find(
            {"parent_id": {"$in": acc_ids}},
            {
                "_id": 0,
                "note": 1,
                "parent_id": 1,
                "created_time": 1,
                "modified_time": 1,
            },
        )
        notes_map = {}
        for note in notes_cursor:
            # 1. Get the parent_id and convert to string
            p_id = note.get("parent_id")

            # 2. If the ID is not in our map yet, initialize an empty list
            if p_id not in notes_map:
                notes_map[p_id] = []

            # 3. Append the note to that ID's list
            notes_map[p_id].append(note)

        return notes_map
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500, detail={"message": "Internal server error"}
        )
