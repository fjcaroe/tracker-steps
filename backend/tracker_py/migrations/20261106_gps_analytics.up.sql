-- Derived telemetry only. Original fixes, assignments and business masters remain unchanged.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
CREATE SEQUENCE IF NOT EXISTS gps_analytics_revision;
CREATE TABLE IF NOT EXISTS gps_analytics_dirty (
 tenant_id varchar(36) NOT NULL, asset_id varchar(36) NOT NULL,
 bucket timestamptz NOT NULL, revision bigint NOT NULL DEFAULT nextval('gps_analytics_revision'),
 PRIMARY KEY (tenant_id,asset_id,bucket)
);
CREATE TABLE IF NOT EXISTS gps_analytics_hourly (
 tenant_id varchar(36) NOT NULL REFERENCES gps_tenants(id),
 asset_id varchar(36) NOT NULL REFERENCES gps_assets(id), bucket timestamptz NOT NULL,
 version integer NOT NULL, metrics jsonb NOT NULL, computed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,asset_id,bucket)
);
CREATE OR REPLACE FUNCTION gps_mark_analytics_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r record; base timestamptz;
BEGIN
 FOR r IN SELECT * FROM (SELECT OLD.tenant_id tid, OLD.asset_id aid, OLD.recorded_at fix_time WHERE TG_OP <> 'INSERT'
                         UNION SELECT NEW.tenant_id, NEW.asset_id, NEW.recorded_at WHERE TG_OP <> 'DELETE') x LOOP
   base := date_trunc('hour', r.fix_time AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
   INSERT INTO gps_analytics_dirty(tenant_id,asset_id,bucket)
   SELECT r.tid,r.aid,base+delta*interval '1 hour' FROM generate_series(-1,1) delta
   WHERE delta=0 OR (delta=-1 AND r.fix_time<base+interval '20 minutes') OR (delta=1 AND r.fix_time>=base+interval '40 minutes')
   ON CONFLICT(tenant_id,asset_id,bucket) DO UPDATE SET revision=nextval('gps_analytics_revision');
 END LOOP;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS gps_positions_analytics_dirty ON gps_positions;
CREATE TRIGGER gps_positions_analytics_dirty AFTER INSERT OR UPDATE OR DELETE ON gps_positions
FOR EACH ROW EXECUTE FUNCTION gps_mark_analytics_dirty();
CREATE INDEX IF NOT EXISTS gps_analytics_dirty_order ON gps_analytics_dirty(bucket,tenant_id,asset_id);
CREATE INDEX IF NOT EXISTS gps_positions_current_assignment ON gps_positions(tenant_id,asset_id,assignment_id,recorded_at DESC,id DESC);
-- Preserve the existing DB role boundary. API readers read aggregates; the
-- existing ingest role maintains only these derived tables and their sequence.
DO $$ DECLARE r record; BEGIN
 FOR r IN SELECT grantee,bool_or(privilege_type='INSERT') writer FROM information_schema.role_table_grants
          WHERE table_schema='public' AND table_name='gps_positions' AND privilege_type IN ('SELECT','INSERT')
            AND grantee<>'PUBLIC' GROUP BY grantee LOOP
   EXECUTE format('GRANT SELECT ON gps_analytics_hourly,gps_analytics_dirty TO %I',r.grantee);
   IF r.writer THEN
     EXECUTE format('GRANT INSERT,UPDATE,DELETE ON gps_analytics_hourly,gps_analytics_dirty TO %I',r.grantee);
     EXECUTE format('GRANT USAGE,SELECT ON SEQUENCE gps_analytics_revision TO %I',r.grantee);
   END IF;
 END LOOP;
END $$;
-- Idempotent backfill queue, including neighbours for cross-hour intervals.
INSERT INTO gps_analytics_dirty(tenant_id,asset_id,bucket)
SELECT DISTINCT tenant_id,asset_id,(date_trunc('hour',recorded_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')+delta*interval '1 hour'
FROM gps_positions CROSS JOIN generate_series(-1,1) delta
ON CONFLICT DO NOTHING;
COMMIT;
