import os
import sys
import psycopg2
from urllib.parse import urlparse

import config


SQL = """
BEGIN;

ALTER TABLE addas
    ADD COLUMN IF NOT EXISTS number TEXT;

-- Best-effort backfill from old combined values like: "Name - 12"
UPDATE addas
SET
    name = TRIM(SPLIT_PART(name, ' - ', 1)),
    number = TRIM(SPLIT_PART(name, ' - ', 2))
WHERE (number IS NULL OR number = '')
  AND name LIKE '% - %';

ALTER TABLE addas
    ALTER COLUMN number SET DEFAULT '';

UPDATE addas SET number = '' WHERE number IS NULL;

ALTER TABLE addas
    ALTER COLUMN number SET NOT NULL;

-- Drop old unique(name) constraint if present
DO $$
DECLARE
    old_constraint_name TEXT;
BEGIN
    SELECT conname
    INTO old_constraint_name
    FROM pg_constraint
    WHERE conrelid = 'addas'::regclass
      AND contype = 'u'
      AND conname = 'addas_name_key';

    IF old_constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE addas DROP CONSTRAINT %I', old_constraint_name);
    END IF;
END $$;

-- New uniqueness: same adda name can exist with different numbers
CREATE UNIQUE INDEX IF NOT EXISTS uq_addas_name_number ON addas(name, number);

COMMIT;
"""


def main() -> int:
    dsn = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")

    # Fallback: build DSN from SUPABASE_URL in config + DB password env.
    if not dsn:
        db_password = os.getenv("SUPABASE_DB_PASSWORD", "").strip()
        db_user = os.getenv("SUPABASE_DB_USER", "postgres").strip() or "postgres"
        supabase_url = (os.getenv("SUPABASE_URL") or getattr(config, "SUPABASE_URL", "")).strip()

        if supabase_url and db_password:
            parsed = urlparse(supabase_url)
            project_ref = (parsed.hostname or "").split(".")[0]
            if project_ref:
                dsn = f"postgresql://{db_user}:{db_password}@db.{project_ref}.supabase.co:5432/postgres"

    if not dsn:
        print("ERROR: Provide DB connection via either:")
        print("  1) SUPABASE_DB_URL / DATABASE_URL, or")
        print("  2) SUPABASE_URL + SUPABASE_DB_PASSWORD (and optional SUPABASE_DB_USER)")
        print("Note: publishable/anon key cannot run schema migrations.")
        return 1

    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(SQL)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        return 1

    print("Migration completed: addas.number column is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
