-- I9: additive only. Existing vehicles, users, routes and telemetry are preserved.
BEGIN;
ALTER TABLE machines ADD COLUMN IF NOT EXISTS passenger_capacity integer;
CREATE TABLE IF NOT EXISTS mobile_passenger_services (
 id uuid PRIMARY KEY, name text NOT NULL,
 route_id uuid NOT NULL REFERENCES mobile_routes(id),
 driver_user_id integer NOT NULL REFERENCES users(id),
 capacity integer NOT NULL CONSTRAINT passenger_service_capacity CHECK (capacity BETWEEN 1 AND 250),
 payload_hash text NOT NULL, created_by integer NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mobile_passenger_services_driver_user_id ON mobile_passenger_services(driver_user_id);
CREATE TABLE IF NOT EXISTS mobile_service_stops (
 id uuid PRIMARY KEY, service_id uuid NOT NULL REFERENCES mobile_passenger_services(id),
 position integer NOT NULL, name text NOT NULL, scheduled_at timestamptz NOT NULL,
 lat double precision, lon double precision,
 CONSTRAINT service_stop_position UNIQUE(service_id,position)
);
CREATE INDEX IF NOT EXISTS ix_mobile_service_stops_service_id ON mobile_service_stops(service_id);
CREATE TABLE IF NOT EXISTS mobile_service_passengers (
 id uuid PRIMARY KEY, service_id uuid NOT NULL REFERENCES mobile_passenger_services(id),
 name text NOT NULL, document text NOT NULL, document_key text NOT NULL,
 boarding_stop_id uuid NOT NULL REFERENCES mobile_service_stops(id),
 alighting_stop_id uuid NOT NULL REFERENCES mobile_service_stops(id),
 seat integer CONSTRAINT service_passenger_seat CHECK (seat IS NULL OR seat>0),
 CONSTRAINT service_passenger_document UNIQUE(service_id,document_key)
);
CREATE INDEX IF NOT EXISTS ix_mobile_service_passengers_service_id ON mobile_service_passengers(service_id);
COMMIT;
