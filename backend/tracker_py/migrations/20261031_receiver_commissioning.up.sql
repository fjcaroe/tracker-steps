-- Preserve all existing records. New fields are commissioning/diagnostic state.
BEGIN;
ALTER TABLE gps_tenants ADD COLUMN IF NOT EXISTS receiver_seen_at timestamptz;
ALTER TABLE gps_tenants ADD COLUMN IF NOT EXISTS receiver_release varchar(80);
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_mode varchar(16) NOT NULL DEFAULT 'disabled';
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_seen_at timestamptz;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_fix_at timestamptz;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_fix_received_at timestamptz;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_lat double precision;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_lon double precision;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_speed double precision;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_error varchar(40);
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_pending integer NOT NULL DEFAULT 0;
ALTER TABLE gps_device_registrations ADD COLUMN IF NOT EXISTS receiver_started_at timestamptz;
COMMIT;
