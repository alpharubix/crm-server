import csv
import io
from datetime import datetime, timezone

from fastapi import Request, UploadFile
from pymongo.database import Database
from starlette import status
from starlette.responses import JSONResponse

from src.utility.MAPPINGS import INVOICE_HEADER_MAPPING



async def upload_invoice_file(request: Request, file: UploadFile, db: Database):
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
                return _error(
                    message=f"Found the header {csv_header} is having no value | Values cannot be empty"
                )

            mapped_row[INVOICE_HEADER_MAPPING[csv_header]] = value

        mapped_rows.append(mapped_row)
        incoming_invoice_no = mapped_row["invoice_no"]

        if incoming_invoice_no in existing_invoice_numbers:
            return _error(
                message=f"Invoice already there in the database | Invoice no : {incoming_invoice_no}"
            )


        incoming_invoice_numbers.add(incoming_invoice_no)

    if not mapped_rows:
        return _error(message="CSV file does not contain any data rows")

    now = datetime.now(timezone.utc)

    for mapped_row in mapped_rows:
        mapped_row["created_at"] = now
        mapped_row["updated_at"] = now
        mapped_row["created_by"] = user_id
        mapped_row["updated_by"] = user_id

    result = collection.insert_many(mapped_rows)
    return {
        "message": "Uploaded successfully",
        "inserted_count": len(result.inserted_ids),
    }
