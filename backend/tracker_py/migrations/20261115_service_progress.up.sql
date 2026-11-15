BEGIN;
CREATE TABLE IF NOT EXISTS mobile_service_progress_events (
    id uuid PRIMARY KEY,
    service_id uuid NOT NULL REFERENCES mobile_passenger_services(id),
    stop_id uuid REFERENCES mobile_service_stops(id),
    sequence integer NOT NULL CONSTRAINT service_progress_positive_sequence CHECK (sequence > 0),
    kind text NOT NULL,
    occurred_at timestamptz NOT NULL,
    actor_id integer NOT NULL REFERENCES users(id),
    notes text,
    signature text,
    manifest_hash text,
    payload_hash text NOT NULL,
    CONSTRAINT service_progress_sequence UNIQUE (service_id, sequence),
    CONSTRAINT service_progress_kind CHECK (
        (kind IN ('arrived', 'departed') AND stop_id IS NOT NULL AND signature IS NULL AND manifest_hash IS NULL)
        OR (kind = 'closed' AND stop_id IS NULL AND signature IS NOT NULL AND manifest_hash IS NOT NULL)
    )
);
COMMIT;
