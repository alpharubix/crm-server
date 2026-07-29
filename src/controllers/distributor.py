from fastapi import Request,requests,UploadFile,File,Depends
from src.utility.MAPPINGS import DIST_HEADER_MAPPING
import csv
import io
from starlette.responses import JSONResponse
from starlette import status
from src.database import get_mongodb
from pymongo.database import Database
from datetime import datetime,timezone
from pathlib import Path

async def upload_file(request:Request,file:UploadFile,db: Database):

    csv_extension = file.filename.lower().endswith(".csv")
    if not csv_extension:
        return JSONResponse(
             status_code=status.HTTP_400_BAD_REQUEST,
             content={
                  "message":f"Invalid file format. Please upload a CSV (.csv) file only.",
                  "data":"WRONG_FILE_TYPE"
             }
        )

    collection = db["distributor_master"]

    user_id = request.state.user_id
    existing_dist_codes = set(collection.distinct("distributor_code"))
    required_headers=set(DIST_HEADER_MAPPING.keys())

    contents = await file.read()

    csv_text = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(csv_text))
    csv_headers = set (reader.fieldnames or [])
    missing_headers = required_headers - csv_headers
    # sales_headers = list()
    print("CSV read Headers : ",csv_headers)
    print("Missing headers : ",missing_headers)

    if missing_headers:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message":"Incomplete field names in the csv file",
                    "data":list(missing_headers)
                }
            )
    
    mapped_rows = []
    incoming_dist_codes=[]

    for row in reader:
        mapped_row = {}

        for csv_header, value in row.items():
            print(f"{csv_header } : {value}")
            if not value:
                 return JSONResponse(
                      status_code=status.HTTP_400_BAD_REQUEST,
                      content={
                           "message":f"Found the header {csv_header} is having no value | Values cannot be empty"
                      }
                 )
            if csv_header.startswith(("Sales", "sales")):
                mapped_row[csv_header] = value
                continue

            # Map all other headers
            mapped_row[DIST_HEADER_MAPPING[csv_header]] = value
            

        mapped_rows.append(mapped_row)
        incoming_dist_code = mapped_row["distributor_code"]
        existing_dist_codes.add(incoming_dist_code)

        if incoming_dist_code in existing_dist_codes:
            return JSONResponse(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 content={
                      "message":f"Distributor already there in the database | Distributor code : {incoming_dist_code}"
                 }
            )
    now = datetime.now(timezone.utc)


    mapped_row["created_at"] = now
    mapped_row["updated_at"]=now
    mapped_row["created_by"]=user_id
    mapped_row["updated_by"]=user_id
    
    result = collection.insert_many(mapped_rows)
    return {
        "message": "Uploaded successfully",
        "distributor_no":incoming_dist_codes
    }

