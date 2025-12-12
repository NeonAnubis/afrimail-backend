-- Migration: Add mailcow_id column to email_aliases table
-- Run this on existing databases to add the mailcow_id column for Mailcow integration
-- Date: 2025-12-12

-- Add mailcow_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'email_aliases'
        AND column_name = 'mailcow_id'
    ) THEN
        ALTER TABLE email_aliases ADD COLUMN mailcow_id TEXT;
        CREATE INDEX IF NOT EXISTS idx_email_aliases_mailcow_id ON email_aliases(mailcow_id);
        RAISE NOTICE 'Added mailcow_id column to email_aliases table';
    ELSE
        RAISE NOTICE 'mailcow_id column already exists in email_aliases table';
    END IF;
END $$;

SELECT 'Migration complete!' AS status;
