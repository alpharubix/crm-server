"""
Migration script: Add company_id column to PostgreSQL audit_logs table if it does not exist.

Usage:
    python add_company_id_to_audit_logs.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import engine
from sqlalchemy import text


def run():
    print("Running migration: Adding company_id column to audit_logs table...")
    try:
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id INTEGER DEFAULT 1;")
            )
            conn.commit()
            print("Successfully verified/added 'company_id' column to 'audit_logs' table.")
    except Exception as e:
        print(f"Error during migration: {e}")


if __name__ == "__main__":
    run()
