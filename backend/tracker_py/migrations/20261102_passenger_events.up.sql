-- I10: immutable event receipts. No existing rows or masters are rewritten.
BEGIN;
CREATE TABLE IF NOT EXISTS mobile_passenger_events (
 id uuid PRIMARY KEY,
 service_id uuid NOT NULL REFERENCES mobile_passenger_services(id),
 passenger_id uuid NOT NULL REFERENCES mobile_service_passengers(id),
 sequence integer NOT NULL CONSTRAINT passenger_event_positive_sequence CHECK(sequence > 0),
 kind text NOT NULL CONSTRAINT passenger_event_kind CHECK(kind IN ('boarded','alighted','no_show')),
 occurred_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
 lat double precision, lon double precision, accuracy_m double precision,
 actor_id integer NOT NULL REFERENCES users(id), payload_hash text NOT NULL,
 CONSTRAINT passenger_event_sequence UNIQUE(service_id,sequence),
 CONSTRAINT passenger_event_coordinates CHECK(
  (lat IS NULL AND lon IS NULL AND accuracy_m IS NULL) OR
  (lat IS NOT NULL AND lon IS NOT NULL AND lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180 AND (accuracy_m IS NULL OR accuracy_m >= 0)))
);
CREATE INDEX IF NOT EXISTS ix_mobile_passenger_events_service_id ON mobile_passenger_events(service_id);
COMMIT;
