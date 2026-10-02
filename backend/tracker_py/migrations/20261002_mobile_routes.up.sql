-- Steps Móvil: rutas asignadas a máquinas. Solo aditivo.
BEGIN;
CREATE TABLE IF NOT EXISTS mobile_routes (
 id uuid PRIMARY KEY, name text NOT NULL, machine_id integer NOT NULL REFERENCES machines(id),
 waypoints json NOT NULL, note text, status text NOT NULL DEFAULT 'assigned',
 created_by integer NOT NULL REFERENCES users(id), created_at timestamptz DEFAULT now(), updated_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_mobile_routes_machine ON mobile_routes(machine_id, status);
COMMIT;
