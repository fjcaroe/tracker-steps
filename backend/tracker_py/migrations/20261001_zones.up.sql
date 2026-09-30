BEGIN;
CREATE TABLE gps_zones (
 id varchar(36) PRIMARY KEY, tenant_id varchar(36) NOT NULL REFERENCES gps_tenants(id),
 name varchar(150) NOT NULL, purpose varchar(30) NOT NULL DEFAULT 'operation',
 color varchar(7) NOT NULL DEFAULT '#6d963c', vertices json NOT NULL,
 active boolean NOT NULL DEFAULT true, version integer NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_gps_zones_tenant_id ON gps_zones(tenant_id);
COMMIT;
