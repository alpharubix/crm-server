from datetime import datetime
from fastapi.exceptions import HTTPException
from pymongo.synchronous.collection import Collection
from starlette.responses import JSONResponse


def insert_notes(user_id, note, parent_id, db):
    try:
        user_coll = db['users']
        acc_coll = db['Accounts']
        notes_coll = db['Notes']

        Owner = user_coll.find_one(
            {'id': str(user_id)},
            {"_id": 0, "id": 1, "first_name": 1, "email": 1}
        )

        Parent_Id = acc_coll.find_one(
            {"id": parent_id},
            {"_id": 0, "id": 1, "Account_Name": 1}
        )

        Modified_By = None

        Created_By = user_coll.find_one(
            {'id': str(user_id)},
            {"_id": 0, "id": 1, "first_name": 1, "email": 1}
        )

        result = notes_coll.insert_one({
            "Owner": Owner,
            "Created_By": Created_By,
            "Modified_By": Modified_By,
            "Note_Content": note,
            "Parent_Id": Parent_Id,
            "Created_Time": datetime.now().isoformat(),
            "Modified_Time": datetime.now().isoformat(),
        })
        print("Insertion result",result)

        return JSONResponse(
            status_code=201,
            content={"message": "Note saved successfully"}
        )

    except Exception as e:
        print(e)
        return JSONResponse(status_code=500, content={"error": str(e)})


def get_notes(acc_ids: list, notes_collection: Collection):
    acc_ids = [str(x) for x in acc_ids]
    try:
        notes_cursor = notes_collection.find(
            {"Parent_Id.id": {"$in": acc_ids}},
            {
                "_id": 0,
                "Owner":1,
                "Note_Content": 1,
                "Parent_Id": 1,
                "Modified_By": 1,
                "Created_By": 1,
                "Created_Time": 1,
                "Modified_Time": 1,
            },
        )
        notes_map = {}
        for note in notes_cursor:
            # 1. Get the parent_id
            p_id = note.get("Parent_Id").get("id")

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
