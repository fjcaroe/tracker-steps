BEGIN;

CREATE TABLE gps_tenants (
	id VARCHAR(36) NOT NULL, 
	issuer VARCHAR(100) NOT NULL, 
	company_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	timezone VARCHAR(80) NOT NULL, 
	retention_days INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (issuer, company_id)
)

;

CREATE TABLE gps_devices (
	id VARCHAR(36) NOT NULL, 
	imei VARCHAR(32) NOT NULL, 
	brand VARCHAR(100) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	firmware VARCHAR(100), 
	protocol VARCHAR(100), 
	freshness_seconds INTEGER NOT NULL, 
	tracking_approved BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (imei)
)

;

CREATE TABLE gps_assets (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	source_id VARCHAR(100) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	plate VARCHAR(40), 
	type VARCHAR(50) NOT NULL, 
	cost_center VARCHAR(200), 
	responsible VARCHAR(200), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, source_id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id)
)

;
CREATE INDEX ix_gps_assets_tenant_id ON gps_assets (tenant_id);

CREATE TABLE gps_view_preferences (
	tenant_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(200) NOT NULL, 
	view_key VARCHAR(80) NOT NULL, 
	value JSON NOT NULL, 
	PRIMARY KEY (tenant_id, user_id, view_key), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id)
)

;

CREATE TABLE gps_assignments (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	device_id VARCHAR(36) NOT NULL, 
	asset_id VARCHAR(36) NOT NULL, 
	valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	valid_to TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id), 
	FOREIGN KEY(device_id) REFERENCES gps_devices (id), 
	FOREIGN KEY(asset_id) REFERENCES gps_assets (id)
)

;
CREATE INDEX ix_gps_assignments_tenant_id ON gps_assignments (tenant_id);
CREATE INDEX ix_gps_assignments_device_id ON gps_assignments (device_id);

CREATE TABLE gps_security_policies (
	asset_id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	armed BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	contacts JSON NOT NULL, 
	zone JSON, 
	allowed_hours_utc JSON NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (asset_id), 
	FOREIGN KEY(asset_id) REFERENCES gps_assets (id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id)
)

;
CREATE INDEX ix_gps_security_policies_tenant_id ON gps_security_policies (tenant_id);

CREATE TABLE gps_security_incidents (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	asset_id VARCHAR(36) NOT NULL, 
	type VARCHAR(40) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	state VARCHAR(30) NOT NULL, 
	responsible VARCHAR(200), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id), 
	FOREIGN KEY(asset_id) REFERENCES gps_assets (id)
)

;
CREATE INDEX ix_gps_security_incidents_tenant_id ON gps_security_incidents (tenant_id);

CREATE TABLE gps_positions (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	device_id VARCHAR(36) NOT NULL, 
	asset_id VARCHAR(36) NOT NULL, 
	assignment_id VARCHAR(36) NOT NULL, 
	source_id VARCHAR(200) NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	lat FLOAT NOT NULL, 
	lon FLOAT NOT NULL, 
	speed_kmh FLOAT, 
	quality VARCHAR(30) NOT NULL, 
	acc BOOLEAN, 
	external_power BOOLEAN, 
	sos BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (device_id, source_id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id), 
	FOREIGN KEY(device_id) REFERENCES gps_devices (id), 
	FOREIGN KEY(asset_id) REFERENCES gps_assets (id), 
	FOREIGN KEY(assignment_id) REFERENCES gps_assignments (id)
)

;
CREATE INDEX gps_position_asset_time ON gps_positions (tenant_id, asset_id, recorded_at, id);

CREATE TABLE gps_audit_events (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	incident_id VARCHAR(36), 
	asset_id VARCHAR(36), 
	actor VARCHAR(200) NOT NULL, 
	action VARCHAR(80) NOT NULL, 
	detail JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id), 
	FOREIGN KEY(incident_id) REFERENCES gps_security_incidents (id)
)

;
CREATE INDEX ix_gps_audit_events_tenant_id ON gps_audit_events (tenant_id);

CREATE TABLE gps_device_commands (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	incident_id VARCHAR(36) NOT NULL, 
	intention_id VARCHAR(100) NOT NULL, 
	type VARCHAR(40) NOT NULL, 
	requester VARCHAR(200) NOT NULL, 
	reason VARCHAR(2000) NOT NULL, 
	state VARCHAR(30) NOT NULL, 
	result VARCHAR(500) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, intention_id), 
	FOREIGN KEY(tenant_id) REFERENCES gps_tenants (id), 
	FOREIGN KEY(incident_id) REFERENCES gps_security_incidents (id)
)

;
CREATE INDEX ix_gps_device_commands_tenant_id ON gps_device_commands (tenant_id);
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE gps_assets ADD CONSTRAINT gps_asset_tenant_pair UNIQUE (id, tenant_id);
ALTER TABLE gps_assignments ADD CONSTRAINT gps_assignment_asset_tenant FOREIGN KEY (asset_id, tenant_id) REFERENCES gps_assets (id, tenant_id);
ALTER TABLE gps_assignments ADD CONSTRAINT gps_assignment_dates CHECK (valid_to IS NULL OR valid_to > valid_from);
ALTER TABLE gps_assignments ADD CONSTRAINT gps_device_no_overlap EXCLUDE USING gist (device_id WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&);
CREATE UNIQUE INDEX gps_asset_current_device ON gps_assignments(asset_id) WHERE valid_to IS NULL;
COMMIT;