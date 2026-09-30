BEGIN;
CREATE TABLE gps_device_registrations (
 id varchar(36) PRIMARY KEY, tenant_id varchar(36) NOT NULL REFERENCES gps_tenants(id),
 device_id varchar(36) NOT NULL UNIQUE REFERENCES gps_devices(id),
 phone varchar(40), operator varchar(100), plan_type varchar(20) NOT NULL DEFAULT 'prepaid',
 apn varchar(100), responsible varchar(200), last_recharged_on date, next_recharge_on date,
 data_expires_on date, line_review_on date, reminder_days integer NOT NULL DEFAULT 7 CHECK (reminder_days BETWEEN 0 AND 90),
 notes varchar(1000), version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_gps_device_registrations_tenant_id ON gps_device_registrations(tenant_id);
-- Only existing, explicit installations establish ownership. No IMEI-based claims.
INSERT INTO gps_device_registrations (id,tenant_id,device_id)
 SELECT device_id,tenant_id,device_id FROM gps_assignments WHERE valid_to IS NULL;
COMMIT;
