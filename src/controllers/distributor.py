import csv
import io
from datetime import datetime, timezone

from fastapi import Request, UploadFile
from pymongo.database import Database
from starlette import status
from starlette.responses import JSONResponse

from src.utility.invoice_csv_headers import DIST_HEADER_MAPPING


def _sales_header_to_field(header: str) -> str:
    normalized = header.strip().lower()
    if not normalized.startswith("sales month "):
        return header

    month_number = normalized.removeprefix("sales month ").strip()
    if month_number.isdigit():
        return f"sales_month_{month_number}"

    return header


async def upload_file(request: Request, file: UploadFile, db: Database):

    csv_extension = bool(file.filename) and file.filename.lower().endswith(".csv")
    if not csv_extension:
        return JSONResponse(
             status_code=status.HTTP_400_BAD_REQUEST,
             content={
                  "message":"Invalid file format. Please upload a CSV (.csv) file only.",
                  "data":"WRONG_FILE_TYPE"
             }
        )

    collection = db["distributor_master"]

    user_id = request.state.user_id
    existing_dist_codes = {
        str(distributor_code).strip()
        for distributor_code in collection.distinct("distributor_code")
        if distributor_code is not None
    }
    required_headers = set(DIST_HEADER_MAPPING.keys())

    contents = await file.read()

    try:
        csv_text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Unable to decode uploaded file. Please upload a valid UTF-8 CSV file.",
                "data": "INVALID_ENCODING",
            },
        )

    reader = csv.DictReader(io.StringIO(csv_text))
    csv_headers = set(reader.fieldnames or [])
    missing_headers = required_headers - csv_headers
    unknown_headers = {
        header
        for header in csv_headers
        if header not in DIST_HEADER_MAPPING and not header.lower().startswith("sales")
    }

    print("CSV read Headers : ", csv_headers)
    print("Missing headers : ", missing_headers)

    if missing_headers:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Incomplete field names in the csv file",
                "data": list(missing_headers)
            }
        )

    if unknown_headers:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Unsupported field names in the csv file",
                "data": list(unknown_headers),
            },
        )

    mapped_rows = []
    incoming_dist_codes = []
    seen_dist_codes = set()

    for row in reader:
        mapped_row = {}

        for csv_header, value in row.items():
            if csv_header is None:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "CSV row has more values than headers",
                        "data": row[csv_header],
                    },
                )

            value = value.strip() if isinstance(value, str) else value
            print(f"{csv_header} : {value}")

            if value is None or value == "":
                 return JSONResponse(
                      status_code=status.HTTP_400_BAD_REQUEST,
                      content={
                           "message":f"Found the header {csv_header} is having no value | Values cannot be empty"
                      }
                 )
            if csv_header.startswith(("Sales", "sales")):
                mapped_row[_sales_header_to_field(csv_header)] = value
                continue

            # Map all other headers
            mapped_row[DIST_HEADER_MAPPING[csv_header]] = value

        incoming_dist_code = str(mapped_row["distributor_code"]).strip()

        if incoming_dist_code in existing_dist_codes:
            return JSONResponse(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 content={
                      "message": f"Distributor already there in the database | Distributor code : {incoming_dist_code}"
                 }
            )

        if incoming_dist_code in seen_dist_codes:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": f"Duplicate distributor code found in the csv file | Distributor code : {incoming_dist_code}"
                },
            )

        seen_dist_codes.add(incoming_dist_code)
        incoming_dist_codes.append(incoming_dist_code)
        mapped_rows.append(mapped_row)

    if not mapped_rows:
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content={
                "message": "Empty file | No distributor data was found",
                "data": None,
            },
        )

    now = datetime.now(timezone.utc)

    for mapped_row in mapped_rows:
        mapped_row["created_at"] = now
        mapped_row["updated_at"] = now
        mapped_row["created_by"] = user_id
        mapped_row["updated_by"] = user_id

    result = collection.insert_many(mapped_rows)
    return {
        "message": "Uploaded successfully",
        "distributor_no": incoming_dist_codes,
        "inserted_count": len(result.inserted_ids),
        "required_distributor_headers": list(required_headers),
        "received_headers": list(csv_headers),
    }

