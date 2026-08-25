"""
Migration script: Add 'notesParentId': null to all existing notes in MongoDB Notes collection
where 'notesParentId' does not exist.

HOW TO RUN (from crm-server root):
    python fix_notes_parent_id.py

Set DRY_RUN = False to actually apply changes.
"""

import os
import sys

# Make sure src is importable
sys.path.insert(0, os.path.dirname(__file__))

from pymongo import MongoClient

from src.config import settings

DRY_RUN = False  # Set to True if you want to preview without changing DB


def run():
    mongo_client = MongoClient(settings.MONGODB_URI)
    # Extract DB name or use default database from client
    mongo_db = mongo_client.get_database()
    notes_coll = mongo_db["Notes"]

    query = {"notesParentId": {"$exists": False}}
    count = notes_coll.count_documents(query)

    print(f"Found {count} note document(s) missing 'notesParentId'.")

    if count == 0:
        print("All notes already have 'notesParentId'. Nothing to update.")
        mongo_client.close()
        return

    if DRY_RUN:
        print(f"[DRY RUN] Would update {count} document(s). Set DRY_RUN=False to apply.")
    else:
        result = notes_coll.update_many(query, {"$set": {"notesParentId": None}})
        print(f"Done. Updated {result.modified_count} note document(s) to set notesParentId = null.")

    mongo_client.close()


if __name__ == "__main__":
    run()
