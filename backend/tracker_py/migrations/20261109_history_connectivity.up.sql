-- Only additive indexes. No requeue, rewrite or deletion of historical records.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
CREATE INDEX IF NOT EXISTS gps_receiver_observation_time
ON gps_audit_events(tenant_id, asset_id, created_at)
WHERE action='receiver_observation';
CREATE INDEX IF NOT EXISTS gps_position_asset_received
ON gps_positions (tenant_id, asset_id, received_at, id);
COMMIT;
