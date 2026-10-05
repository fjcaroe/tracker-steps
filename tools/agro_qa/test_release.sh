#!/usr/bin/env bash
set -euo pipefail
ARCHIVE=${1:?archive}
SHA=${2:?sha256}
LABEL=${3:?development or demo}
SUFFIX=${4:-}
case "$SUFFIX" in '') ;; PHASEB) ;; *) exit 2 ;; esac
case "$LABEL" in
  development) SOURCE=LAB_TAREAS; CONFIG=/etc/dev_odoo18.conf; ROLE=dev_odoo18; SERVICE=odoo18-dev.service; DATA=/opt/dev_odoo18/.local/share/Odoo ;;
  demo) SOURCE=STEPS_DEMO; CONFIG=/etc/demo_odoo18.conf; ROLE=demo_odoo18; SERVICE=odoo18-demo.service; DATA=/opt/demo_odoo18/.local/share/Odoo ;;
  *) exit 2 ;;
esac
test "$(sha256sum "$ARCHIVE" | cut -d ' ' -f1)" = "$SHA"
DB=AGRO_INTEGRATION_QA_20261005_${LABEL^^}
ROOT=/opt/steps-agro-qa/$LABEL
if [ "$SUFFIX" = PHASEB ]; then
  DB=${DB}_PHASEB
  ROOT=$ROOT/phaseb
fi
RUN_USER=$(systemctl show --value --property=User "$SERVICE")
test -n "$RUN_USER" && test "$RUN_USER" != root
RUN_GROUP=$(id -gn "$RUN_USER")
sudo install -d -m 0755 -o "$RUN_USER" -g "$RUN_GROUP" "$ROOT" "$ROOT/addons" "$ROOT/data"
sudo tar -xzf "$ARCHIVE" -C "$ROOT/addons" --no-same-owner
sudo chown -R "$RUN_USER:$RUN_GROUP" "$ROOT/addons" "$ROOT/data"
if ! sudo -u postgres psql -Atc "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -qx 1; then
  sudo -u postgres pg_dump -Fc "$SOURCE" > "$ROOT/source.dump"
  sudo chmod 0600 "$ROOT/source.dump"
  sudo chown postgres:postgres "$ROOT/source.dump"
  sudo -u postgres createdb -O "$ROLE" "$DB"
fi
if ! sudo -u postgres psql -d "$DB" -Atc "SELECT to_regclass('public.ir_module_module') IS NOT NULL" | grep -qx t; then
  sudo chown postgres:postgres "$ROOT/source.dump"
  sudo -u postgres psql -d "$DB" -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;'
  sudo -u postgres pg_restore --no-owner --no-comments --role="$ROLE" -d "$DB" "$ROOT/source.dump"
fi
  # Isolated clones do not send email or run scheduled jobs.
  sudo -u postgres psql -d "$DB" -v ON_ERROR_STOP=1 -c "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;"
  if sudo test -d "$DATA/filestore/$SOURCE" && ! sudo test -d "$ROOT/data/filestore/$DB"; then
    sudo install -d -m 0755 -o "$RUN_USER" -g "$RUN_GROUP" "$ROOT/data/filestore/$DB"
    sudo cp -a --reflink=auto "$DATA/filestore/$SOURCE/." "$ROOT/data/filestore/$DB/"
    sudo chown -R "$RUN_USER:$RUN_GROUP" "$ROOT/data/filestore/$DB"
  fi
LOG="$ROOT/tests-$(date -u +%Y%m%dT%H%M%SZ).log"
if [ "$SUFFIX" = PHASEB ] && ! sudo test -s "$ROOT/migration-before.json"; then
  sudo install -m 0600 -o postgres -g postgres /dev/null "$ROOT/migration-before.json"
  sudo -u postgres /usr/bin/python3.10 /tmp/check_migration_preservation.py "$LABEL" before
fi
BASE_ADDONS=$(/usr/bin/python3.10 -c 'import configparser,sys; c=configparser.ConfigParser(interpolation=None); c.read(sys.argv[1]); print(c["options"]["addons_path"])' "$CONFIG")
MODULES=step_export,step_producers,step_inventory_packing,step_producer_fruit_flow,step_packing_operations
set +e
sudo -u "$RUN_USER" /usr/bin/python3.10 /opt/odoo18/odoo-bin -c "$CONFIG" -d "$DB" \
  --addons-path="$ROOT/addons,$BASE_ADDONS" \
  --data-dir="$ROOT/data" --workers=0 --max-cron-threads=0 --no-http \
  --http-interface=127.0.0.1 --http-port=0 --without-demo=all \
  -i "$MODULES" -u "$MODULES" --test-enable \
  --test-tags /step_export,/step_producers,/step_inventory_packing,/step_producer_fruit_flow,/step_packing_operations \
  --stop-after-init --logfile="$LOG"
RESULT=$?
set -e
if [ "$RESULT" -ne 0 ]; then
  sudo tail -n 85 "$LOG"
  printf 'AGRO_QA_TEST_FAILED DB=%s LOG=%s\n' "$DB" "$LOG"
  exit "$RESULT"
fi
sudo grep -E '0 failed|ERROR|FAIL|modules loaded' "$LOG" | tail -n 35
if [ "$SUFFIX" = PHASEB ]; then
  sudo -u postgres /usr/bin/python3.10 /tmp/check_migration_preservation.py "$LABEL" after
fi
printf 'AGRO_QA_TEST_OK DB=%s LOG=%s\n' "$DB" "$LOG"
