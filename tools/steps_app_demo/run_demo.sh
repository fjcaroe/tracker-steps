#!/usr/bin/env bash
# Demostración reproducible de Steps App contra un Odoo REAL con datos SINTÉTICOS.
#
# Requisitos (ver docs/STEPS_APP_DEMO.md): checkout de Odoo 18 + venv, PostgreSQL local con un rol «odoo» (superusuario), y el addon
# step_mobilization (rama develop) en $EXTRA_ADDONS. La base se llama «demo»: el script la BORRA y la recrea. NUNCA apuntarlo a una base real.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ODOO_HOME="${ODOO_HOME:-/opt/odoo-env}"
ODOO_SRC="${ODOO_SRC:-$ODOO_HOME/odoo}"
EXTRA_ADDONS="${EXTRA_ADDONS:-$ODOO_HOME/extra}"
VENV="${VENV:-$ODOO_HOME/venv}"
DB="${DB:-demo}"
PORT="${PORT:-8070}"
PGUSER_ODOO="${PGUSER_ODOO:-odoo}"
PGPASS_ODOO="${PGPASS_ODOO:-odoo}"
case "$DB" in demo*|test*) ;; *) echo "Se rechaza la base '$DB': debe llamarse demo* o test*." >&2; exit 2;; esac

export DEMO_PASSWORD="${DEMO_PASSWORD:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(12)+"-Aa1")')}"
export DEMO_SUMMARY="${DEMO_SUMMARY:-$ODOO_HOME/demo-summary.json}"   # fuera del repositorio
export STEPS_DEMO_SUMMARY="$DEMO_SUMMARY" STEPS_E2E_BASE="http://localhost:$PORT" STEPS_E2E_DB="$DB"
ADDONS="$ODOO_SRC/addons,$EXTRA_ADDONS,$REPO"
odoo() { ( . "$VENV/bin/activate"; cd "$ODOO_SRC"; python odoo-bin "$@" --addons-path="$ADDONS" --db_host=localhost --db_user="$PGUSER_ODOO" --db_password="$PGPASS_ODOO" ); }

echo "== 1/5 Recreando la base '$DB' e instalando los módulos"
PGPASSWORD="$PGPASS_ODOO" dropdb -h localhost -U "$PGUSER_ODOO" --if-exists "$DB"
odoo -d "$DB" -i step_mobile_portal,step_mobile_portal_colaciones,step_mobile_portal_mobilization,step_mobile_portal_tracker \
     --stop-after-init --without-demo=all --log-level=warn

echo "== 2/5 Sembrando datos sintéticos"
( . "$VENV/bin/activate"; cd "$ODOO_SRC"; python odoo-bin shell -d "$DB" --addons-path="$ADDONS" --db_host=localhost --db_user="$PGUSER_ODOO" --db_password="$PGPASS_ODOO" --log-level=warn < "$REPO/tools/steps_app_demo/seed.py" ) | grep -E "DEMO_SEED_OK|Resumen"

echo "== 3/5 Levantando Odoo en el puerto $PORT"
odoo -d "$DB" --http-port="$PORT" --db-filter="^$DB\$" --log-level=warn >"$ODOO_HOME/odoo-$DB.log" 2>&1 &
ODOO_PID=$!
trap 'kill $ODOO_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -fsS "http://localhost:$PORT/steps_app/v1/health" >/dev/null 2>&1 && break; sleep 2; done
curl -fsS "http://localhost:$PORT/steps_app/v1/health"; echo

echo "== 4/5 Recorrido de aceptación (cliente de Steps ↔ Odoo)"
( cd "$REPO/mobile" && npm run test:e2e )

echo "== 5/5 Listo. Contraseña de demostración y datos: $DEMO_SUMMARY (fuera del repositorio)"
