BEGIN;
DROP INDEX IF EXISTS ix_work_orders_assigned;
ALTER TABLE work_orders DROP COLUMN IF EXISTS progress_pct, DROP COLUMN IF EXISTS mobile_status, DROP COLUMN IF EXISTS scheduled_time, DROP COLUMN IF EXISTS assigned_user_id;
DROP TABLE IF EXISTS mobile_diagnostics, mobile_devices, mobile_expenses, mobile_checklists, mobile_incidents;
COMMIT;
