#!/usr/bin/env bash
# Run on odoo-new. Only the requested Odoo environments receive the new portal.
set -euo pipefail
release=${TRACKER_RELEASE:-/tmp/tracker-steps-deploy}
chmod 755 "$release"
target=/opt/fernando_odoo18/apis/backend/tracker_py
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=${TRACKER_BACKUP:-/opt/backups/tracker-portal-$stamp}
if [ -z "${TRACKER_BACKUP:-}" ]; then
sudo install -d -m 700 "$backup"
sudo cp -a "$target" "$backup/tracker_py"
sudo cp -a /etc/nginx "$backup/nginx"
for db in tracker_steps LAB_TAREAS STEPS_DEMO CERRO_EL_PLOMO; do
    sudo -u postgres pg_dump -Fc "$db" | sudo tee "$backup/$db.dump" >/dev/null
    sudo -u postgres pg_restore --list < <(sudo cat "$backup/$db.dump") >/dev/null
done
echo "BACKUP=$backup"
sudo sh -c "cd '$backup' && sha256sum *.dump > SHA256SUMS"
fi

# Rehearse both directions on a database restored from the real Tracker backup.
testdb=TRACKER_LAYOUT_QA_$stamp
sudo -u postgres createdb "$testdb"
sudo cat "$backup/tracker_steps.dump" | sudo -u postgres pg_restore --no-owner -d "$testdb"
sudo -u postgres psql -d "$testdb" -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20260930_fleet_protection.up.sql" >/dev/null
sudo -u postgres psql -d "$testdb" -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20260930_fleet_protection.down.sql" >/dev/null
sudo -u postgres psql -d "$testdb" -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20260930_fleet_protection.up.sql" >/dev/null
echo "MIGRATION_REHEARSAL=$testdb"

# Refuse to overwrite unrelated edits in deployed API sources.
python3 - "$release" "$target" <<'PY'
import pathlib, subprocess, sys
release, target = map(pathlib.Path, sys.argv[1:])
for p in (target/'app').rglob('*.py'):
    rel = p.relative_to(target).as_posix()
    result = subprocess.run(['git','-C',str(release),'show','9aa55c15a0f3bb3fd28127ea260191ad4632b6e8:backend/tracker_py/'+rel],capture_output=True)
    current = (release/'backend/tracker_py'/rel)
    if result.returncode != 0 or p.read_text().replace('\r\n','\n') != result.stdout.decode().replace('\r\n','\n'):
        if not current.exists() or p.read_text().replace('\r\n','\n') != current.read_text().replace('\r\n','\n'):
            raise SystemExit('Server drift requires review: '+rel)
PY
sudo rsync -a --delete --exclude '.env' --exclude '.venv' --exclude '__pycache__' "$release/backend/tracker_py/" "$target/"
sudo chown -R fernandocaro1198_gmail_com "$target"
sudo -u postgres psql -d tracker_steps -v ON_ERROR_STOP=1 -f "$target/migrations/20260930_fleet_protection.up.sql" >/dev/null
sudo -u postgres psql -d tracker_steps -v ON_ERROR_STOP=1 -c 'GRANT ALL ON ALL TABLES IN SCHEMA public TO fcaror;' >/dev/null
if ! sudo test -e /etc/tracker-bridge-keys.json; then
    sudo install -o postgres -g postgres -m 600 /dev/null /etc/tracker-bridge-keys.json
    echo '{}' | sudo tee /etc/tracker-bridge-keys.json >/dev/null
fi
sudo -u postgres /usr/bin/python3.10 "$release/scripts/tracker-portal-provision.py"
sudo chgrp "$(id -gn fernandocaro1198_gmail_com)" /etc/tracker-bridge-keys.json
sudo chmod 640 /etc/tracker-bridge-keys.json
sudo systemctl restart tracker-steps-api.service
for attempt in $(seq 1 20); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null; then break; fi
    sleep 1
done
curl -fsS http://127.0.0.1:8000/openapi.json | python3 -c 'import json,sys; p=json.load(sys.stdin)["paths"]; assert "/v1/fleet/snapshot" in p and "/v1/security/incidents" in p; print("V1_OPENAPI_OK")'

# Build from a fresh clone with production browser configuration, never print env.
cd "$release"
sudo cp /opt/fernando_odoo18/apis/tracker-steps/.env .env
cp /opt/fernando_odoo18/apis/tracker-steps/.env.production .env.production
sudo chown "$(whoami)" .env
chmod 600 .env .env.production
npm ci --no-audit --no-fund
VITE_ODOO_PORTAL=true npm run build
sudo install -d -o root -g odoo /var/www/web_tracker_portal
sudo rsync -a --delete --chown=root:odoo dist/ /var/www/web_tracker_portal/

# Add-on rehearsal in an isolated Odoo copy, before installing in the real DBs.
sudo cp -a /opt/dev_odoo18/odoo_agriculture/step_tracker_odoo "$backup/step_tracker_odoo-dev"
sudo rsync -a "$release/step_tracker_portal/" /opt/dev_odoo18/odoo_agriculture/step_tracker_portal/
sudo chown -R odoo:odoo /opt/dev_odoo18/odoo_agriculture/step_tracker_portal
odootest=TRACKER_ODOO_QA_$stamp
sudo -u postgres createdb -O dev_odoo18 "$odootest"
sudo cat "$backup/LAB_TAREAS.dump" | sudo -u postgres pg_restore --no-owner --role=dev_odoo18 -d "$odootest"
sudo -u odoo env PYTHONPATH=/opt/odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf -d "$odootest" -i step_tracker_portal --stop-after-init --no-http --max-cron-threads=0 --logfile=/tmp/tracker-portal-qa.log
echo "ODOO_REHEARSAL=$odootest"

deploy_odoo() {
    local db=$1 service=$2 user=$3 config=$4 addons=$5 port=$6 host=$7
    sudo -u postgres psql -d "$db" -At -c "SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');" > /tmp/tracker-pending-modules
    test ! -s /tmp/tracker-pending-modules
    sudo systemctl stop "$service"
    trap 'sudo systemctl start "$service"' RETURN
    sudo rsync -a "$release/step_tracker_portal/" "$addons/step_tracker_portal/"
    sudo chown -R "$user" "$addons/step_tracker_portal"
    if ! sudo -u "$user" env PYTHONPATH=/opt/odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin -c "$config" -d "$db" -i step_tracker_portal --stop-after-init --no-http --max-cron-threads=0 --logfile="/tmp/tracker-portal-$db.log"; then
        sudo systemctl start "$service"
        echo "ODOO_INSTALL_FAILED=$db; see /tmp/tracker-portal-$db.log" >&2
        return 1
    fi
    sudo systemctl start "$service"
    trap - RETURN
    for attempt in $(seq 1 40); do
        if curl -fsS -H "Host: $host" "http://127.0.0.1:$port/web/login" >/dev/null; then break; fi
        sleep 1
    done
    curl -fsS -H "Host: $host" "http://127.0.0.1:$port/web/login" >/dev/null
    sudo -u postgres psql -d "$db" -At -c "SELECT name,state,latest_version FROM ir_module_module WHERE name='step_tracker_portal';"
}
deploy_odoo LAB_TAREAS odoo18-dev.service odoo /etc/dev_odoo18.conf /opt/dev_odoo18/odoo_agriculture 8075 desarrollo.stepsapp.cl
deploy_odoo STEPS_DEMO odoo18-demo.service demo_odoo18 /etc/demo_odoo18.conf /opt/demo_odoo18/odoo_agriculture 8080 demo.stepsapp.cl
deploy_odoo CERRO_EL_PLOMO odoo18-cerroelplomo.service cerro_odoo18 /etc/odoo18-cerroelplomo.conf /opt/cerroelplomo_odoo18/steps_addons 8082 cerroelplomo.stepsapp.cl

sudo tee /etc/nginx/snippets/steps-tracker-portal.conf >/dev/null <<'NGINX'
location = /web_tracker { return 301 /web_tracker/; }
location ^~ /web_tracker/assets/ {
    alias /var/www/web_tracker_portal/assets/;
    add_header Cache-Control "public, max-age=31536000, immutable";
}
location ^~ /web_tracker/ {
    alias /var/www/web_tracker_portal/;
    try_files $uri $uri/ /web_tracker/index.html;
    add_header Cache-Control "no-cache";
}
NGINX
sudo python3 "$release/scripts/tracker-portal-nginx.py"
sudo nginx -t
sudo systemctl reload nginx

sudo tee /etc/systemd/system/steps-tracker-signal.service >/dev/null <<'UNIT'
[Unit]
Description=Steps GPS communication monitor
After=tracker-steps-api.service
[Service]
Type=oneshot
User=fernandocaro1198_gmail_com
WorkingDirectory=/opt/fernando_odoo18/apis/backend/tracker_py
Environment=PYTHONPATH=/opt/fernando_odoo18/apis/backend/tracker_py
ExecStart=/opt/fernando_odoo18/apis/backend/tracker_py/.venv/bin/python scripts/check_gps_signal.py
UNIT
sudo tee /etc/systemd/system/steps-tracker-signal.timer >/dev/null <<'UNIT'
[Unit]
Description=Check GPS freshness every minute
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now steps-tracker-signal.timer
sudo systemctl start steps-tracker-signal.service
expected=$(grep -o 'assets/index-[^" ]*\.js' /var/www/web_tracker_portal/index.html)
for host in desarrollo.stepsapp.cl demo.stepsapp.cl cerroelplomo.stepsapp.cl; do
    actual=$(curl -fsS "https://$host/web_tracker/" | grep -o 'assets/index-[^" ]*\.js')
    test "$actual" = "$expected"
    curl -fsS "https://$host/web_tracker/$actual" >/dev/null
    echo "VERIFIED=$host/$actual"
done
echo "RELEASE=$(git rev-parse HEAD) BACKUP=$backup"
