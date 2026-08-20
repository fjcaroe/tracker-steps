BEGIN;

ALTER TABLE implements
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_implements_is_active
    ON implements (is_active);

COMMIT;
