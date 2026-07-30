import csv
import io
from datetime import datetime, timezone
from logging import basicConfig
from math import ceil
import logging
from fastapi import Request, UploadFile
from pymongo import UpdateOne
from pymongo.database import Database
from starlette import status
from starlette.responses import JSONResponse
from src.utility.invoice_csv_headers import INVOICE_HEADER_MAPPING, DIST_HEADER_MAPPING
basicConfig(level=logging.INFO)

async def upload_distributor_csv(request:Request,file:UploadFile,db: Database):
    try:

        distributor_collection = db["distributor_master"]
        distributor_master_history_collection = db["distributor_master_history"]
        creation_rows = []  # this list holds the dict of rows which are need to be created
        updated_rows = []  # this list holds the dict of rows which are need to be updated
        update_rows_current_data = []  # this array holds all the current state of the updated distcode data
        empty_values_row = []  # this list holds the dict of missing fields in the row with row id
        row_iterator = 2  # points to the current row
        total_row_created = 0
        total_row_updated = 0
        user_id = request.state.user_id
        required_headers=set(DIST_HEADER_MAPPING.keys())
        contents = await file.read()
        csv_text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(csv_text))
        csv_headers = set (reader.fieldnames or [])
        missing_headers = list(required_headers - csv_headers)
        print("CSV read Headers : ",csv_headers)
        print("Missing headers : ",missing_headers)
        print("Type of missing headers",type(missing_headers))

        #step 1: validating the headers
        if missing_headers:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message":"Header miss match found",
                        "data":missing_headers
                    }
                )

        for row in reader:
            mapped_row = {}
            row_missing_values = {}
            for csv_header, value in row.items():
                #step2 : checking for empty values in row

                if not value:
                    if row_missing_values.get("row_number") is None:
                        row_missing_values.update({"row_number":row_iterator,"empty_fields":[csv_header]})
                    else:
                        missing_fields_list = row_missing_values["empty_fields"]
                        row_missing_values.update({"row_number":row_iterator,"empty_fields":missing_fields_list.append(csv_header)})

                #step 3 :Adding additional column into the database
                if csv_header.startswith(("Sales", "sales")):
                    mapped_row[csv_header] = value
                    continue

                # Map all other headers
                mapped_row[DIST_HEADER_MAPPING[csv_header]] = value

            if row_missing_values:
               empty_values_row.append(row_missing_values)
               continue
            #step 4: split the rows into insertion and updation based on the distcode
            incoming_dist_code = mapped_row["distributor_code"]

            distributor = distributor_collection.find_one({"distributor_code":incoming_dist_code})

            if distributor: 
                updated_rows.append(mapped_row) 
                update_rows_current_data.append(distributor)
            else:
                creation_rows.append(mapped_row)

        #step 5: update and insert the data to the collection
        now = datetime.now(timezone.utc)

        if creation_rows:

            for row in creation_rows: #adding meta tags to the creation row
                row["created_at"] = now
                row["updated_at"] = now
                row["created_by"] = user_id
                row["updated_by"] = user_id
            logging.info(msg=f"rows for creation {creation_rows}")
            created_rows = distributor_collection.insert_many(creation_rows)
            total_row_created = len(created_rows.inserted_ids)

        if updated_rows:
            update_history,updated_fields = updated_field_detector(
                updated_rows,
                update_rows_current_data,
                now,
                user_id,
                "distributor_code"
            )
            print("UPDATED DISTRIBUTOR DATA",updated_fields)
            print("Updated DISTRIBUTOR DATA History",update_history)
            if update_history and updated_fields:
                bulk_ops = [
                    UpdateOne(
                        {"distributor_code": row["distributor_code"]},
                        {"$set": {"updated_at": now, "updated_by": user_id,
                                  **{k: v for k, v in row.items() if k != "distributor_code"}}}
                    )
                    for row in updated_fields
                ]
                logging.info(msg=f"bulk updation {bulk_ops}")
                distributor_collection.bulk_write(bulk_ops)
                total_row_updated = len(updated_fields)
                distributor_master_history_collection.insert_many(update_history)

        return {
            "message": "Uploaded successfully",
            "total_rows_craeted":total_row_created,
            "total_rows_updated":total_row_updated,
            "failed_rows":empty_values_row,
        }
    except Exception as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message":"Internal Server Error","data":None}
        )

def updated_field_detector(updated_row,updated_row_current_data,updated_at,updated_by,unique_filed):
    iterator = 0
    updated_fields_history = [] #holds the history of the updated fields
    updated_rows = [] #holds which field from which row is being updated

    for incoming_row in updated_row:
        updated_row_dict = {}
        unique_code = incoming_row.get(unique_filed)
        old_row_current_field_data = updated_row_current_data[iterator]

        for key, value in incoming_row.items():
            old_value = old_row_current_field_data.get(key)
            new_value = value
            if old_value != new_value:
                updated_fields_history.append({
                    unique_filed: unique_code,
                    "field_name": key,
                     f"old_{key}": old_value,
                    f"new_{key}":new_value,
                    "updated_at": updated_at,
                    "updated_by": updated_by,
                })
                if updated_row_dict.get(unique_filed):
                    updated_row_dict.update({key:new_value})
                else:
                    updated_row_dict.update({unique_filed:unique_code,key:value})
        if updated_row_dict:
            updated_rows.append(updated_row_dict)
        iterator+=1
    return updated_fields_history,updated_rows


async def upload_invoice_file(request:Request,file:UploadFile,db: Database):
    try:

        invoice_collection = db["invoice_master"]
        invoice_master_history_collection = db["invoice_master_history"]
        creation_rows = []  # this list holds the dict of rows which are need to be created
        updated_rows = []  # this list holds the dict of rows which are need to be updated
        update_rows_current_data = []  # this array holds all the current state of the updated invoice data
        empty_values_row = []  # this list holds the dict of missing fields in the row with row id
        row_iterator = 2  # points to the current row
        total_row_created = 0
        total_row_updated = 0
        user_id = request.state.user_id
        required_headers=set(INVOICE_HEADER_MAPPING.keys())
        contents = await file.read()
        csv_text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(csv_text))
        csv_headers = set (reader.fieldnames or [])
        missing_headers = list(required_headers - csv_headers)
        print("CSV read Headers : ",csv_headers)
        print("Missing headers : ",missing_headers)
        print("Type of missing headers",type(missing_headers))

        #step 1: validating the headers
        if missing_headers:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message":"Header miss match found",
                        "data":missing_headers
                    }
                )

        for row in reader:
            mapped_row = {}
            row_missing_values = {}
            for csv_header, value in row.items():
                #step2 : checking for empty values in row

                if not value:
                    if row_missing_values.get("row_number") is None:
                        row_missing_values.update({"row_number":row_iterator,"empty_fields":[csv_header]})
                    else:
                        row_missing_values["empty_fields"].append(csv_header)

                # Map all other headers
                if csv_header in INVOICE_HEADER_MAPPING:
                    mapped_row[INVOICE_HEADER_MAPPING[csv_header]] = value

            if row_missing_values:
               empty_values_row.append(row_missing_values)
               row_iterator += 1
               continue
               
            #step 4: split the rows into insertion and updation based on the invoice_no
            incoming_invoice_no = mapped_row.get("invoice_no")
            
            if not incoming_invoice_no:
                # If invoice_no itself is missing or empty, handle it
                if not row_missing_values:
                    empty_values_row.append({"row_number": row_iterator, "empty_fields": ["Invoice no"]})
                row_iterator += 1
                continue

            invoice = invoice_collection.find_one({"invoice_no":incoming_invoice_no})

            if invoice: 
                updated_rows.append(mapped_row) 
                update_rows_current_data.append(invoice)
            else:
                creation_rows.append(mapped_row)
            
            row_iterator += 1

        #step 5: update and insert the data to the collection
        now = datetime.now(timezone.utc)

        if creation_rows:

            for row in creation_rows: #adding meta tags to the creation row
                row["created_at"] = now
                row["updated_at"] = now
                row["created_by"] = user_id
                row["updated_by"] = user_id
            logging.info(msg=f"rows for creation {creation_rows}")
            created_rows = invoice_collection.insert_many(creation_rows)
            total_row_created = len(created_rows.inserted_ids)

        if updated_rows:
            update_history,updated_fields = updated_field_detector(
                updated_rows,
                update_rows_current_data,
                now,
                user_id,
                "invoice_no"
            )
            print("UPDATED INVOICE DATA",updated_fields)
            print("Updated INVOICE DATA History",update_history)
            if update_history and updated_fields:
                bulk_ops = [
                    UpdateOne(
                        {"invoice_no": row["invoice_no"]},
                        {"$set": {"updated_at": now, "updated_by": user_id,
                                  **{k: v for k, v in row.items() if k != "invoice_no"}}}
                    )
                    for row in updated_fields
                ]
                logging.info(msg=f"bulk updation {bulk_ops}")
                invoice_collection.bulk_write(bulk_ops)
                total_row_updated = len(updated_fields)
                invoice_master_history_collection.insert_many(update_history)

        return {
            "message": "Uploaded successfully",
            "total_rows_craeted":total_row_created,
            "total_rows_updated":total_row_updated,
            "failed_rows":empty_values_row,
        }
    except Exception as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message":"Internal Server Error","data":None}
        )

        
async def get_distributors(
    request: Request,
    db: Database,
    page: int = 1,
    limit: int = 10,
):
    try:
        distributor_collection = db["distributor_master"]

        # Validate page and limit
        limit = max(limit, 1)

        skip = (int(page) - 1) * limit


        # Fetch data
        distributors = distributor_collection.find({},{"_id":0}).skip(skip).limit(limit).to_list(length=limit)

        #serialize objects to strings
        pointer=0
        for distributor in distributors:
            for key,value in distributor.items():
                if isinstance(value, datetime):
                    distributors[pointer].update({key:value.isoformat()})
                if isinstance(value, int):
                    distributors[pointer].update({key:str(value)})

            pointer+=1

        total_records = distributor_collection.count_documents({})

        pagination = {
            "page": int(page),
            "limit": limit,
            "total_records": total_records,
            "total_pages": ceil(len(distributors) / limit) ,
        }


        return JSONResponse(status_code=status.HTTP_200_OK,content={
            "message": "Distributor data fetched successfully",
            "data": {"distributors":distributors,"page_info":pagination}
        })

    except Exception as e:
        print(str(e))
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,content={"message":"Internal server error","data":None})


async def get_invoices(
    request: Request,
    db: Database,
    page: int = 1,
    limit: int = 10,
):
    try:
        invoice_collection = db["invoice_master"]

        # Validate page and limit
        limit = max(limit, 1)

        skip = (int(page) - 1) * limit

        # Fetch data
        invoices = invoice_collection.find({}, {"_id": 0}).skip(skip).limit(limit).to_list(length=limit)

        #serialize objects to strings
        pointer = 0
        for invoice in invoices:
            for key, value in invoice.items():
                if isinstance(value, datetime):
                    invoices[pointer].update({key: value.isoformat()})
                if isinstance(value, int):
                    invoices[pointer].update({key: str(value)})

            pointer += 1

        total_records = invoice_collection.count_documents({})

        pagination = {
            "page": int(page),
            "limit": limit,
            "total_records": total_records,
            "total_pages": ceil(len(invoices) / limit),
        }

        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "message": "Invoice data fetched successfully",
            "data": {"invoices": invoices, "page_info": pagination}
        })

    except Exception as e:
        print(str(e))
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": "Internal server error", "data": None})


