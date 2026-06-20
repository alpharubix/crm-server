"""
One-time migration: Fix old Candidate notes stored with wrong Parent_Id structure.

Problem: Old notes for module="Candidates" were saved with:
  - "deal_name" key instead of "candidate_name" in Parent_Id
  - Value showing a deal name instead of the real candidate name

This script:
  1. Finds all Candidate module notes with "deal_name" in Parent_Id
  2. Resolves the real candidate_name from PostgreSQL using Parent_Id.id
  3. Replaces "deal_name" → "candidate_name" with correct value

HOW TO RUN (from crm-server root):
    python fix_candidate_notes.py

Set DRY_RUN = False to actually apply changes.
"""

import sys
import os

# Make sure src is importable
sys.path.insert(0, os.path.dirname(__file__))

from pymongo import MongoClient
from src.database import SessionLocal
from src.models.hiring import Candidate
from src.config import settings

# ── CONFIG ──────────────────────────────────────────────────────────────────
DRY_RUN = True   # ← Set to False to actually apply changes
# ────────────────────────────────────────────────────────────────────────────


def run():
    # Connect to MongoDB using the same URI from settings
    mongo_client = MongoClient(settings.MONGODB_URI)
    mongo_db = mongo_client["crm_dev"]
    notes_coll = mongo_db["Notes"]

    # Find all Candidate notes that still have the old "deal_name" key
    bad_notes = list(notes_coll.find(
        {"module": "Candidates", "Parent_Id.deal_name": {"$exists": True}},
        {"_id": 1, "Parent_Id": 1, "Note_Content": 1}
    ))

    print(f"Found {len(bad_notes)} candidate note(s) with wrong structure.")
    if not bad_notes:
        print("Nothing to fix. All good!")
        return

    # Collect unique candidate IDs from these notes
    candidate_ids = list({
        int(n["Parent_Id"]["id"])
        for n in bad_notes
        if n.get("Parent_Id", {}).get("id")
    })
    print(f"Candidate IDs involved: {candidate_ids}")

    # Fetch real candidate names from PostgreSQL
    with SessionLocal() as pg_db:
        rows = pg_db.query(Candidate.id, Candidate.candidate_name) \
                    .filter(Candidate.id.in_(candidate_ids)) \
                    .all()
        id_to_name = {str(row.id): row.candidate_name for row in rows}

    print(f"Resolved {len(id_to_name)} name(s) from PostgreSQL: {id_to_name}")
    print()

    fixed = 0
    for note in bad_notes:
        note_id = note["_id"]
        parent_id_str = note.get("Parent_Id", {}).get("id")
        old_value = note.get("Parent_Id", {}).get("deal_name", "?")
        candidate_name = id_to_name.get(parent_id_str, "Unknown")

        print(f"  [{note_id}] content='{note.get('Note_Content')}' | "
              f"id={parent_id_str} | old deal_name='{old_value}' → new candidate_name='{candidate_name}'")

        if DRY_RUN:
            continue

        # Rename deal_name → candidate_name with the correct resolved value
        notes_coll.update_one(
            {"_id": note_id},
            {
                "$set": {"Parent_Id.candidate_name": candidate_name},
                "$unset": {"Parent_Id.deal_name": ""}
            }
        )
        fixed += 1

    print()
    if DRY_RUN:
        print(f"[DRY RUN] Would fix {len(bad_notes)} note(s). Set DRY_RUN=False to apply.")
    else:
        print(f"Done. Fixed {fixed} note(s).")

    mongo_client.close()


if __name__ == "__main__":
    run()
