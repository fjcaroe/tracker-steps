-- Steps Móvil I4-I15: incidencias, checklists, gastos de ruta, dispositivos, diagnósticos y asignación de tareas. Solo aditivo.
BEGIN;
CREATE TABLE IF NOT EXISTS mobile_incidents (
 id uuid PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id),
 session_id uuid REFERENCES tracking_sessions(id), machine_id integer REFERENCES machines(id),
 cost_center_id integer REFERENCES cost_centers(id), category text NOT NULL, note text,
 lat double precision, lon double precision, occurred_at timestamptz NOT NULL, photo_path text,
 status text NOT NULL DEFAULT 'open', handled_by integer REFERENCES users(id), handled_at timestamptz,
 created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mobile_incidents_status ON mobile_incidents(status, occurred_at DESC);
CREATE TABLE IF NOT EXISTS mobile_checklists (
 id uuid PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id),
 session_id uuid REFERENCES tracking_sessions(id), machine_id integer NOT NULL REFERENCES machines(id),
 items json NOT NULL, all_ok boolean NOT NULL DEFAULT true, occurred_at timestamptz NOT NULL,
 created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS mobile_expenses (
 id uuid PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id),
 session_id uuid REFERENCES tracking_sessions(id), work_order_id integer REFERENCES work_orders(id),
 machine_id integer REFERENCES machines(id), kind text NOT NULL, liters numeric(10,2), amount numeric(14,2),
 station text, odometer numeric(12,2), note text, occurred_at timestamptz NOT NULL, photo_path text,
 created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mobile_expenses_user ON mobile_expenses(user_id, occurred_at DESC);
CREATE TABLE IF NOT EXISTS mobile_devices (
 user_id integer PRIMARY KEY REFERENCES users(id), version text, platform text, pending integer,
 last_sync_at timestamptz, last_seen_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS mobile_diagnostics (
 id serial PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id), version text, message text, log text,
 created_at timestamptz DEFAULT now()
);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS assigned_user_id integer REFERENCES users(id);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS scheduled_time text;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS mobile_status text;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS progress_pct integer;
CREATE INDEX IF NOT EXISTS ix_work_orders_assigned ON work_orders(assigned_user_id) WHERE assigned_user_id IS NOT NULL;
COMMIT;
