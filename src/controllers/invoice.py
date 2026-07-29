import csv
import io
from datetime import datetime, timezone

from fastapi import Request, UploadFile
from pymongo.database import Database
from starlette import status
from starlette.responses import JSONResponse
from pathlib import Path
from src.utility.MAPPINGS import INVOICE_HEADER_MAPPING



async def upload_invoice_file(request: Request, file: UploadFile, db: Database):

    csv_extension = file.filename.lower().endswith(".csv")
    if not csv_extension:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message":f"Invalid file format. Please upload a CSV (.csv) file only.",
                    "data":"WRONG_FILE_TYPE"
                }
        )
    collection = db["invoice_master"]

    user_id = request.state.user_id
    existing_invoice_numbers = set(collection.distinct("invoice_no"))
    required_headers = set(INVOICE_HEADER_MAPPING.keys())

    contents = await file.read()

    csv_text = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    csv_headers = set(reader.fieldnames or [])
    missing_headers = required_headers - csv_headers

    print("CSV read Headers : ", csv_headers)
    print("Missing headers : ", missing_headers)

    incoming_invoices=[]
    if missing_headers:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message":f"Missing fields in the invoice : {missing_headers}",
                "data":missing_headers
            }
        )
    mapped_rows = []

    for row in reader:
        mapped_row = {}

        for csv_header, value in row.items():
            print(f"{csv_header} : {value}")
            if not value:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message":""
                    }
                )

            mapped_row[INVOICE_HEADER_MAPPING[csv_header]] = value

        mapped_rows.append(mapped_row)

        incoming_invoice_no = mapped_row["invoice_no"]

        if incoming_invoice_no in existing_invoice_numbers:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message":"Invoice number is already existing",
                    "data":incoming_invoice_no
                }
            )


        incoming_invoices.append(incoming_invoice_no)

    if not mapped_rows:
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content={
                "message":"Empty file | No invoice data was found",
                "data":None
            }
        )

    now = datetime.now(timezone.utc)

    for mapped_row in mapped_rows:
        mapped_row["created_at"] = now
        mapped_row["updated_at"] = now
        mapped_row["created_by"] = user_id
        mapped_row["updated_by"] = user_id

    result = collection.insert_many(mapped_rows)
    response = {
        "message": "Uploaded successfully",
        "invoices_recieved":incoming_invoices,
        "inserted_count": len(result.inserted_ids),
        "required_invoice_headers":required_headers,
        "received_headers":csv_headers,
        "missing_headers":missing_headers if len(missing_headers)>0 else None
    }
    print("Response : \n",response)
    return ""
