#!/usr/bin/env python3
"""
Migration script to add missing columns to existing database tables.
Run this after updating the codebase to apply database schema changes.

Usage:
    cd backend
    python scripts/run_migration.py
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine


async def run_migrations():
    """Run all pending migrations."""
    print("Running database migrations...")

    async with engine.begin() as conn:
        # Migration 1: Add mailcow_id to email_aliases
        print("\n[1/1] Checking email_aliases.mailcow_id column...")
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'email_aliases' AND column_name = 'mailcow_id'
        """))
        if result.fetchone() is None:
            print("  -> Adding mailcow_id column...")
            await conn.execute(text("""
                ALTER TABLE email_aliases ADD COLUMN mailcow_id TEXT
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_email_aliases_mailcow_id ON email_aliases(mailcow_id)
            """))
            print("  -> Done!")
        else:
            print("  -> Column already exists, skipping.")

    print("\nAll migrations completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migrations())
