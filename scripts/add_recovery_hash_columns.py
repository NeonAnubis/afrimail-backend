"""
Migration script to add recovery_email_hash and recovery_phone_hash columns.
Run with: python -m scripts.add_recovery_hash_columns
"""

import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def run_migration():
    """Add hash columns for recovery email and phone."""
    async with AsyncSessionLocal() as session:
        # Add recovery_email_hash column if it doesn't exist
        await session.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users_extended'
                    AND column_name = 'recovery_email_hash'
                ) THEN
                    ALTER TABLE users_extended
                    ADD COLUMN recovery_email_hash VARCHAR(64);
                    CREATE INDEX IF NOT EXISTS idx_users_recovery_email_hash
                    ON users_extended(recovery_email_hash);
                END IF;
            END $$;
        """))

        # Add recovery_phone_hash column if it doesn't exist
        await session.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users_extended'
                    AND column_name = 'recovery_phone_hash'
                ) THEN
                    ALTER TABLE users_extended
                    ADD COLUMN recovery_phone_hash VARCHAR(64);
                    CREATE INDEX IF NOT EXISTS idx_users_recovery_phone_hash
                    ON users_extended(recovery_phone_hash);
                END IF;
            END $$;
        """))

        await session.commit()
        print("Migration completed: Added recovery hash columns")


if __name__ == "__main__":
    asyncio.run(run_migration())
