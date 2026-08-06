import csv
import io
from datetime import datetime, timezone
from logging import basicConfig
from math import ceil
import logging
import re
from typing import Optional
from fastapi import Request, UploadFile
from pymongo import UpdateOne
from pymongo.database import Database
from starlette import status
from starlette.responses import JSONResponse, StreamingResponse
from src.utility.invoice_csv_headers import *
from src.utility.utils import str_to_date

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
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin1"): #encoding fix
            try:
                csv_text = contents.decode(encoding)
                print(f"Decoded using {encoding}")
                break
            except UnicodeDecodeError:
                return JSONResponse(status_code=400,content={
                        "message":"Header miss match found",
                        "data":"File encoding is not supported"
                    })
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
                if csv_header.startswith(("Sales", "sales")):
                    mapped_row[csv_header] = value
                    continue

                if not value:
                    if csv_header in DIST_MASTER_MANDATORY_FIELDS:
                        if row_missing_values.get("row_number") is None:
                            row_missing_values["row_number"] = row_iterator
                            row_missing_values["empty_fields"] = [csv_header]
                        else:
                            row_missing_values["empty_fields"].append(csv_header)
                        continue

                        # Map all other headers
                if csv_header in DIST_HEADER_MAPPING:
                    if csv_header.lower() in {"Data Received", "Enrollment Date"}:
                        mapped_row[DIST_HEADER_MAPPING[csv_header]] = str_to_date(value)
                    else:
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
                "distributor_code",
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
            "total_rows_created":total_row_created,
            "total_rows_updated":total_row_updated,
            "failed_rows":empty_values_row,
            }
    except  ValueError as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Invalid date format", "data": None}
        )

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


async def upload_invoice_csv(request:Request,file:UploadFile,db: Database):
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
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin1"): #encoding fix
            try:
                csv_text = contents.decode(encoding)
                print(f"Decoded using {encoding}")
                break
            except UnicodeDecodeError:
                return JSONResponse(status_code=400,content={
                        "message":"Header miss match found",
                        "data":"File encoding is not supported"
                    })
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
                    if csv_header in INVOICE_MASTER_MANDATORY_FIELDS:
                        if row_missing_values.get("row_number") is None:
                            row_missing_values["row_number"] = row_iterator
                            row_missing_values["empty_fields"] = [csv_header]
                        else:
                            row_missing_values["empty_fields"].append(csv_header)
                        continue

                # Map all other headers
                if csv_header in INVOICE_HEADER_MAPPING:
                    if "date" in csv_header.lower():
                        mapped_row[INVOICE_HEADER_MAPPING[csv_header]] = str_to_date(value)
                    else:
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
    except  ValueError as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Invalid date format", "data": None}
        )
    except Exception as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message":"Internal Server Error","data":None}
        )

def _serialize_uploaded_records(records):
    for record in records:
        for key, value in list(record.items()):
            if isinstance(value, datetime):
                record[key] = value.isoformat()
            if isinstance(value, int):
                record[key] = str(value)
    return records


def _get_uploaded_collection_data(
    request: Request,
    db: Database,
    collection_name: str,
    response_key: str,
    success_message: str,
    data_filter:dict = None,
    page: int = 1,
    limit: int = 10,
    is_export = False,
):
    try:
        if data_filter is None:
            data_filter = {}

        collection = db[collection_name]

        page = max(int(page), 1)
        limit = max(int(limit), 1)
        skip = (page - 1) * limit

        if is_export:
            records = collection.find(data_filter, {"_id": 0}).to_list(length=None)
            records = _serialize_uploaded_records(records)
            return records #custom output for handling the export request

        records = collection.find(data_filter, {"_id": 0}).skip(skip).limit(limit).to_list(length=limit)
        records = _serialize_uploaded_records(records)

        total_records = collection.count_documents(data_filter)

        pagination = {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": ceil(total_records / limit) if total_records else 0,
        }

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": success_message,
                "data": {response_key: records, "page_info": pagination},
            },
        )

    except Exception as e:
        print(str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message":"Internal server error","data":None}
        )



async def _process_csv_upload(
    request: Request,
    file: UploadFile,
    db: Database,
    mapping: dict,
    collection_name: str,
    history_collection_name: str,
    unique_key: str,
    mandatory_keys: list,
):
    try:
        if file.filename is None:
            return JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
                content={
                    "message":"Please input the invoice file",
                    "data":None
                }
            )
        collection = db[collection_name]
        history_collection = db[history_collection_name]
        creation_rows = []
        updated_rows = []
        update_rows_current_data = []
        empty_values_row = []
        row_iterator = 2
        total_row_created = 0
        total_row_updated = 0
        user_id = request.state.user_id
        required_headers = set(mapping.keys())
        contents = await file.read()
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin1"): #encoding fix
            try:
                csv_text = contents.decode(encoding)
                print(f"Decoded using {encoding}")
                break
            except UnicodeDecodeError:
                return JSONResponse(status_code=400,content={
                        "message":"Header miss match found",
                        "data":"File encoding is not supported"
                    })
        reader = csv.DictReader(io.StringIO(csv_text))
        csv_headers = set(reader.fieldnames or [])
        missing_headers = list(required_headers - csv_headers)

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
                if not value:
                    if csv_header in mandatory_keys:
                        if row_missing_values.get("row_number") is None:
                            row_missing_values["row_number"] = row_iterator
                            row_missing_values["empty_fields"] = [csv_header]
                        else:
                            row_missing_values["empty_fields"].append(csv_header)
                        continue

                if csv_header.startswith(("Sales", "sales")):
                    mapped_row[csv_header] = value
                    continue

                if csv_header in mapping:
                    if "date" in csv_header.lower():
                        mapped_row[mapping[csv_header]] = str_to_date(value)
                    else:
                        mapped_row[mapping[csv_header]] = value

            if row_missing_values:
                empty_values_row.append(row_missing_values)
                row_iterator += 1
                continue
                
            incoming_unique_code = mapped_row.get(unique_key)
            if not incoming_unique_code:
                empty_values_row.append({"row_number": row_iterator, "empty_fields": [unique_key]})
                row_iterator += 1
                continue

            existing_record = collection.find_one({unique_key: incoming_unique_code})

            if existing_record: 
                updated_rows.append(mapped_row) 
                update_rows_current_data.append(existing_record)
            else:
                creation_rows.append(mapped_row)
                
            row_iterator += 1

        now = datetime.now(timezone.utc)

        if creation_rows:
            for row in creation_rows:
                row["created_at"] = now
                row["updated_at"] = now
                row["created_by"] = user_id
                row["updated_by"] = user_id
            created_rows = collection.insert_many(creation_rows)
            total_row_created = len(created_rows.inserted_ids)

        if updated_rows:
            update_history, updated_fields = updated_field_detector(
                updated_rows,
                update_rows_current_data,
                now,
                user_id,
                unique_key
            )
            if update_history and updated_fields:
                bulk_ops = [
                    UpdateOne(
                        {unique_key: row[unique_key]},
                        {"$set": {"updated_at": now, "updated_by": user_id,
                                  **{k: v for k, v in row.items() if k != unique_key}}}
                    )
                    for row in updated_fields
                ]
                collection.bulk_write(bulk_ops)
                total_row_updated = len(updated_fields)
                history_collection.insert_many(update_history)

        return {
            "message": "Uploaded successfully",
            "total_rows_created": total_row_created,
            "total_rows_updated": total_row_updated,
            "failed_rows": empty_values_row,
        }
    except  ValueError as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Invalid date format", "data": None}
        )
    except Exception as e:
        logging.error(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message":"Internal Server Error","data":None}
        )

def _list_to_csv(data: list[dict]):
    output = io.StringIO()

    if not data:
        return output

    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)

    output.seek(0)
    return output

def _csv_export_orchestration(datas):
    csv_file = _list_to_csv(datas)

    return StreamingResponse(
        csv_file,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="transactions.csv"'
        },
    )



async def upload_kotak_hwc_transaction_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=KOTAK_HWC_TRANS_MAPPING, 
        collection_name="kotak_hwc_transaction", 
        history_collection_name="kotak_hwc_transaction_history", 
        unique_key="invoice_number",
        mandatory_keys=KOTAK_HWC_TRANS_MANDATORY_FIELDS
    )

async def upload_kotak_hwc_credit_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=KOTAK_HWC_CREDIT_MAPPING, 
        collection_name="kotak_hwc_credit", 
        history_collection_name="kotak_hwc_credit_history", 
        unique_key="dealer_name",
        mandatory_keys=KOTAK_HWC_CREDIT_MANDATORY_FIELDS
    )

async def upload_tcpl_transaction_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=TCPL_TRANS_MAPPING, 
        collection_name="tcpl_transaction", 
        history_collection_name="tcpl_transaction_history", 
        unique_key="invoice_no",
        mandatory_keys=TCPL_TRANS_MANDATORY_FIELDS
    )

async def upload_tcpl_credit_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=TCPL_CREDIT_MAPPING, 
        collection_name="tcpl_credit", 
        history_collection_name="tcpl_credit_history", 
        unique_key="account_id",
        mandatory_keys=TCPL_CREDIT_MANDATORY_FIELDS
    )

async def upload_hero_transaction_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=HERO_TRANS_MAPPING, 
        collection_name="hero_transaction", 
        history_collection_name="hero_transaction_history", 
        unique_key="invoice_number",
        mandatory_keys=HERO_TRANS_MANDATORY_FIELDS
    )


async def upload_hero_credit_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=HERO_CREDIT_MAPPING, 
        collection_name="hero_credit", 
        history_collection_name="hero_credit_history", 
        unique_key="invoice_number",
        mandatory_keys=HERO_CREDIT_MANDATORY_FIELDS
    )

async def upload_kotak_ckpl_transaction_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=KOTAK_CKPL_TRANS_MAPPING, 
        collection_name="kotak_ckpl_transaction", 
        history_collection_name="kotak_ckpl_transaction_history", 
        unique_key="invoice_number",
        mandatory_keys=KOTAK_CKPL_CREDIT_MANDATORY_FIELDS
    )

async def upload_kotak_ckpl_credit_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=KOTAK_CKPL_CREDIT_MAPPING, 
        collection_name="kotak_ckpl_credit", 
        history_collection_name="kotak_ckpl_credit_history", 
        unique_key="dealer_name",
        mandatory_keys=KOTAK_CKPL_CREDIT_MANDATORY_FIELDS
    )

async def upload_muthoot_transaction_csv(request: Request, file: UploadFile, db: Database):
    print("MUTHOOT TRANSACTION CSV READING")
    return await _process_csv_upload(
        request, file, db, 
        mapping=MUTHOOT_TRANS_MAPPING, 
        collection_name="muthoot_transaction", 
        history_collection_name="muthoot_transaction_history", 
        unique_key="invoice_number",
        mandatory_keys=MUTHOOT_TRANS_MANDATORY_FIELDS
    )

async def upload_muthoot_credit_csv(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db, 
        mapping=MUTHOOT_CREDIT_MAPPING, 
        collection_name="muthoot_credit", 
        history_collection_name="muthoot_credit_history", 
        unique_key="loan_account_number",
        mandatory_keys=MUTHOOT_CREDIT_MANDATORY_FIELDS
    )

async def upload_consolidated_report(request: Request, file: UploadFile, db: Database):
    return await _process_csv_upload(
        request, file, db,
        mapping=CONSOLIDATED_LIMIT_MAPPING,
        collection_name="consolidated_limit_report",
        history_collection_name="consolidated_limit_history_report",
        unique_key="distributor_code",
        mandatory_keys=CONSOLIDATED_LIMIT_MANDATORY_FIELDS
    )

async def get_distributors(
    request: Request,
    db: Database,
    page: int = 1,
    anchor: str = None,
    region: str = None,
    state: str = None,
    distribution_type: str = None,
    division: str = None,
    limit: int = 10,
    is_export: bool = False,
):

    filter = {}

    if anchor:
        filter["anchor"] = {
            "$regex": f"^{re.escape(anchor)}",
            "$options": "i"
        }

    if region:
        filter["region"] = {
            "$regex": f"^{re.escape(region)}",
            "$options": "i"
        }

    if state:
        filter["state"] = {
            "$regex": f"^{re.escape(state)}",
            "$options": "i"
        }

    if distribution_type:
        filter["distribution_type"] = {
            "$regex": f"^{re.escape(distribution_type)}",
            "$options": "i"
        }

    if division:
        filter["division"] = {
            "$regex": f"^{re.escape(division)}",
            "$options": "i"
        }

    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="distributor_master",
        response_key="distributors",
        success_message="Distributor data fetched successfully",
        data_filter=filter,
        page=page,
        limit=limit,
        is_export=True
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="distributor_master",
        response_key="distributors",
        success_message="Distributor data fetched successfully",
        data_filter=filter,
        page=page,
        limit=limit,
    )


async def get_kotak_hwc_transactions(
    request: Request,
    db: Database,
    dealer_name: str | None = None,
    invoice_date: str | None = None,
    invoice_number: str | None = None,
    disbursement_date: str | None = None,
    overdue_within_cure: str | None = None,
    overdue_beyond_cure: str | None = None,
    page: int = 1,
    limit: int = 10,
    is_export: bool = False,
):
    filter = {}

    if dealer_name:
        filter["dealer_name"] = {
            "$regex": f"^{re.escape(dealer_name)}",
            "$options": "i"
        }

    if invoice_date:
        filter["invoice_date"] = str_to_date(invoice_date)

    if invoice_number:
        filter["invoice_number"] = {
            "$regex": f"^{re.escape(invoice_number)}",
            "$options": "i"
        }

    if disbursement_date:
        filter["disbursement_date"] = str_to_date(disbursement_date)

    if overdue_within_cure:
        filter["overdue_within_cure"] = {
            "$regex": f"^{re.escape(overdue_within_cure)}",
            "$options": "i"
        }

    if overdue_beyond_cure:
        filter["overdue_beyond_cure"] = {
            "$regex": f"^{re.escape(overdue_beyond_cure)}",
            "$options": "i"
        }

    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        data_filter=filter,
        collection_name="kotak_hwc_transaction",
        response_key="kotak_hwc_transactions",
        success_message="Kotak HWC transaction data fetched successfully",
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)


    return _get_uploaded_collection_data(
        request=request,
        db=db,
        data_filter=filter,
        collection_name="kotak_hwc_transaction",
        response_key="kotak_hwc_transactions",
        success_message="Kotak HWC transaction data fetched successfully",
        page=page,
        limit=limit,
    )


async def get_kotak_hwc_credits(
    request: Request,
    db: Database,
    dealer_name: str | None = None,
    distributor_code: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if dealer_name:
        data_filter["dealer_name"] = {
            "$regex": f"^{re.escape(dealer_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="kotak_hwc_credit",
        response_key="kotak_hwc_credits",
        success_message="Kotak HWC credit data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="kotak_hwc_credit",
        response_key="kotak_hwc_credits",
        success_message="Kotak HWC credit data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_kotak_ckpl_transactions(
    request: Request,
    db: Database,
    dealer_name: str | None = None,
    invoice_date: str | None = None,
    invoice_number: str | None = None,
    disbursement_date: str | None = None,
    overdue_within_cure: str | None = None,
    overdue_beyond_cure: str | None = None,
    is_export:bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if dealer_name:
        data_filter["dealer_name"] = {
            "$regex": f"^{re.escape(dealer_name)}",
            "$options": "i"
        }

    if invoice_date:
        data_filter["invoice_date_id"] = {
            "$regex": f"^{re.escape(invoice_date)}",
            "$options": "i"
        }

    if invoice_number:
        data_filter["invoice_number"] = {
            "$regex": f"^{re.escape(invoice_number)}",
            "$options": "i"
        }

    if disbursement_date:
        data_filter["disbursement_date"] = str_to_date(disbursement_date)

    if overdue_within_cure:
        data_filter["overdue_within_cure_inr"] = {
            "$regex": f"^{re.escape(overdue_within_cure)}",
            "$options": "i"
        }

    if overdue_beyond_cure:
        data_filter["overdue_beyondcure_inr"] = {
            "$regex": f"^{re.escape(overdue_beyond_cure)}",
            "$options": "i"
        }

    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="kotak_ckpl_transaction",
        response_key="kotak_ckpl_transactions",
        success_message="Kotak CKPL transaction data fetched successfully",
        data_filter=data_filter,
        page=page,
        is_export=True,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return  _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="kotak_ckpl_transaction",
        response_key="kotak_ckpl_transactions",
        success_message="Kotak CKPL transaction data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_kotak_ckpl_credits(
    request: Request,
    db: Database,
    dealer_name: str | None = None,
    distributor_code: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if dealer_name:
        data_filter["dealer_name"] = {
            "$regex": f"^{re.escape(dealer_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="kotak_ckpl_credit",
        response_key="kotak_ckpl_credits",
        success_message="Kotak CKPL credit data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="kotak_ckpl_credit",
        response_key="kotak_ckpl_credits",
        success_message="Kotak CKPL credit data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_tcpl_transactions(
    request: Request,
    db: Database,
    customer_name: str | None = None,
    invoice_no: str | None = None,
    invoice_date: str | None = None,
    dpd: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if customer_name:
        data_filter["customer_name"] = {
            "$regex": f"^{re.escape(customer_name)}",
            "$options": "i"
        }

    if invoice_no:
        data_filter["invoice_no"] = {
            "$regex": f"^{re.escape(invoice_no)}",
            "$options": "i"
        }

    if invoice_date:
        data_filter["invoice_date"] = str_to_date(invoice_date)

    if dpd:
        data_filter["dpd"] = {
            "$regex": f"^{re.escape(dpd)}",
            "$options": "i"
        }

    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="tcpl_transaction",
        response_key="tcpl_transactions",
        success_message="TCPL transaction data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="tcpl_transaction",
        response_key="tcpl_transactions",
        success_message="TCPL transaction data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_tcpl_credits(
    request: Request,
    db: Database,
    dealer_name: str | None = None,
    distributor_code: str | None = None,
    is_export:bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if dealer_name:
        data_filter["client_name"] = {
            "$regex": f"^{re.escape(dealer_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="tcpl_credit",
        response_key="tcpl_credits",
        success_message="TCPL credit data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="tcpl_credit",
        response_key="tcpl_credits",
        success_message="TCPL credit data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_hero_transactions(
    request: Request,
    db: Database,
    client_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    dpd: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if client_name:
        data_filter["client_name"] = {
            "$regex": f"^{re.escape(client_name)}",
            "$options": "i"
        }

    if invoice_number:
        data_filter["invoice_number"] = {
            "$regex": f"^{re.escape(invoice_number)}",
            "$options": "i"
        }

    if invoice_date:
        data_filter["invoice_date"] = str_to_date(invoice_date)

    if dpd:
        data_filter["dpd"] = {
            "$regex": f"^{re.escape(dpd)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="hero_transaction",
        response_key="hero_transactions",
        success_message="Hero transaction data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="hero_transaction",
        response_key="hero_transactions",
        success_message="Hero transaction data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_hero_credits(
    request: Request,
    db: Database,
    customer_name: str | None = None,
    distributor_code: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if customer_name:
        data_filter["customer_name"] = {
            "$regex": f"^{re.escape(customer_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="hero_credit",
        response_key="hero_credits",
        success_message="Hero credit data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="hero_credit",
        response_key="hero_credits",
        success_message="Hero credit data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_muthoot_transactions(
    request: Request,
    db: Database,
    borrower_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    principal_dpd: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    import re

    if borrower_name:
        data_filter["borrower_name"] = {
            "$regex": f"^{re.escape(borrower_name)}",
            "$options": "i"
        }

    if invoice_number:
        data_filter["invoice_number"] = {
            "$regex": f"^{re.escape(invoice_number)}",
            "$options": "i"
        }

    if invoice_date:
        data_filter["invoice_date"] = str_to_date(invoice_date)

    if principal_dpd:
        data_filter["principal_dpd"] = {
            "$regex": f"^{re.escape(principal_dpd)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="muthoot_transaction",
        response_key="muthoot_transactions",
        success_message="Muthoot transaction data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="muthoot_transaction",
        response_key="muthoot_transactions",
        success_message="Muthoot transaction data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_muthoot_credits(
    request: Request,
    db: Database,
    borrower_name: str | None = None,
    distributor_code: str | None = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}


    if borrower_name:
        data_filter["borrower_name"] = {
            "$regex": f"^{re.escape(borrower_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }
    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="muthoot_credit",
        response_key="muthoot_credits",
        success_message="Muthoot credit data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)

    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="muthoot_credit",
        response_key="muthoot_credits",
        success_message="Muthoot credit data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_invoices(
    request: Request,
    db: Database,
    anchor: Optional[str] = None,
    processed_by: Optional[str] = None,
    working_date: Optional[str] = None,
    lender_name: Optional[str] = None,
    distributor_name: Optional[str] = None,
    distributor_code: Optional[str] = None,
    invoice_no: Optional[str] = None,
    loan_disbursement_date: Optional[str] = None,
    utr: Optional[str] = None,
    status: Optional[str] = None,
    status_reason: Optional[str] = None,
    is_export:bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}


    if anchor:
        data_filter["anchor"] = {
            "$regex": f"^{re.escape(anchor)}",
            "$options": "i"
        }

    if processed_by:
        data_filter["processed_by"] = {
            "$regex": f"^{re.escape(processed_by)}",
            "$options": "i"
        }

    if working_date:
        data_filter["working_date"] = str_to_date(working_date)

    if lender_name:
        data_filter["lender_name"] = {
            "$regex": f"^{re.escape(lender_name)}",
            "$options": "i"
        }

    if distributor_name:
        data_filter["distributor_name"] = {
            "$regex": f"^{re.escape(distributor_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }

    if invoice_no:
        data_filter["invoice_no"] = {
            "$regex": f"^{re.escape(invoice_no)}",
            "$options": "i"
        }

    if loan_disbursement_date:
        data_filter["loan_disbursement_date"] = str_to_date(loan_disbursement_date)

    if utr:
        data_filter["utr"] = {
            "$regex": f"^{re.escape(utr)}",
            "$options": "i"
        }

    if status:
        data_filter["status"] = {
            "$regex": f"^{re.escape(status)}",
            "$options": "i"
        }

    if status_reason:
        data_filter["status_reason"] = {
            "$regex": f"^{re.escape(status_reason)}",
            "$options": "i"
        }

    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="invoice_master",
        response_key="invoices",
        success_message="Invoice data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)


    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="invoice_master",
        response_key="invoices",
        success_message="Invoice data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )


async def get_consolidated_limit_report(
    request: Request,
    db: Database,
    company_name: str = None,
    distributor_code: str = None,
    state: str = None,
    lender: str = None,
    anchor_id: str = None,
    billing_status: str = None,
    is_export: bool = False,
    page: int = 1,
    limit: int = 10,
):
    data_filter = {}

    if company_name:
        data_filter["company_name"] = {
            "$regex": f"^{re.escape(company_name)}",
            "$options": "i"
        }

    if distributor_code:
        data_filter["distributor_code"] = {
            "$regex": f"^{re.escape(distributor_code)}",
            "$options": "i"
        }

    if state:
        data_filter["state"] = {
            "$regex": f"^{re.escape(state)}",
            "$options": "i"
        }

    if lender:
        data_filter["lender"] = {
            "$regex": f"^{re.escape(lender)}",
            "$options": "i"
        }

    if anchor_id:
        data_filter["anchor_id"] = {
            "$regex": f"^{re.escape(anchor_id)}",
            "$options": "i"
        }

    if billing_status:
        data_filter["billing_status"] = {
            "$regex": f"^{re.escape(billing_status)}",
            "$options": "i"
        }

    if is_export:
        datas = _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="consolidated_limit_report",
        response_key="consolidated_limit_report",
        success_message="limit report data fetched successfully",
        data_filter=data_filter,
        is_export=True,
        page=page,
        limit=limit,
    )
        return _csv_export_orchestration(datas)


    return _get_uploaded_collection_data(
        request=request,
        db=db,
        collection_name="consolidated_limit_report",
        response_key="consolidated_limit_report",
        success_message="limit report data fetched successfully",
        data_filter=data_filter,
        page=page,
        limit=limit,
    )
