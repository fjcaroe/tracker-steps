#!/usr/bin/env bash
# Incremental upgrade after the initial Tracker portal installation.
set -euo pipefail
release=${TRACKER_RELEASE:?Set fresh checkout directory}
base=407d7df
target=/opt/fernando_odoo18/apis/backend/tracker_py
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/backups/tracker-mobility-$stamp
chmod 755 "$release"
cd "$release"
for db in LAB_TAREAS STEPS_DEMO CERRO_EL_PLOMO; do
  pending=$(sudo -u postgres psql -d "$db" -At -c "SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');")
  test "$pending" = 0
done
# Scope writes to the known release delta; refuse unrelated server changes.
python3 - "$release" "$target" "$base" <<'PY'
import pathlib, subprocess, sys
release,target,base=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),sys.argv[3]
files=['app/main.py','app/models/fleet.py','app/routers/fleet.py','requirements.txt','scripts/assign_gps.py']
for rel in files:
    old=subprocess.check_output(['git','-C',str(release),'show',base+':backend/tracker_py/'+rel]).decode().replace('\r\n','\n')
    actual=(target/rel).read_text().replace('\r\n','\n')
    new=(release/'backend/tracker_py'/rel).read_text().replace('\r\n','\n')
    if actual not in (old,new):raise SystemExit('Unreviewed server drift: '+rel)
for directory in ['/opt/dev_odoo18/odoo_agriculture','/opt/demo_odoo18/odoo_agriculture','/opt/cerroelplomo_odoo18/steps_addons']:
    for rel in ['__manifest__.py','controllers/portal.py','views/menu.xml']:
        old=subprocess.check_output(['git','-C',str(release),'show',base+':step_tracker_portal/'+rel]).decode().replace('\r\n','\n')
        actual=(pathlib.Path(directory)/'step_tracker_portal'/rel).read_text().replace('\r\n','\n')
        new=(release/'step_tracker_portal'/rel).read_text().replace('\r\n','\n')
        if actual not in (old,new):raise SystemExit('Unreviewed addon drift: '+directory+'/'+rel)
PY
sudo install -d -m 700 "$backup"
for db in tracker_steps LAB_TAREAS STEPS_DEMO CERRO_EL_PLOMO; do
  sudo -u postgres pg_dump -Fc "$db" | sudo tee "$backup/$db.dump" >/dev/null
  sudo cat "$backup/$db.dump" | sudo -u postgres pg_restore --list >/dev/null
done
sudo cp -a "$target" "$backup/tracker_py"
sudo cp -a /var/www/web_tracker_portal "$backup/web_tracker_portal"
sudo cp -a /opt/dev_odoo18/odoo_agriculture/step_tracker_portal "$backup/addon-dev"
sudo cp -a /opt/demo_odoo18/odoo_agriculture/step_tracker_portal "$backup/addon-demo"
sudo cp -a /opt/cerroelplomo_odoo18/steps_addons/step_tracker_portal "$backup/addon-cerro"
sudo sh -c "cd '$backup' && sha256sum *.dump > SHA256SUMS"
echo "BACKUP=$backup"
# Build with server-held browser settings; never print their contents.
sudo cp /opt/fernando_odoo18/apis/tracker-steps/.env .env
sudo cp /opt/fernando_odoo18/apis/tracker-steps/.env.production .env.production
sudo chown "$(whoami)" .env .env.production
chmod 600 .env .env.production
npm ci --no-audit --no-fund
VITE_ODOO_PORTAL=true npm run build
rm -- "$release/.env" "$release/.env.production"

testdb=TRACKER_CONFIG_QA_$stamp
sudo -u postgres createdb "$testdb"
sudo cat "$backup/tracker_steps.dump" | sudo -u postgres pg_restore --no-owner -d "$testdb"
sudo -u postgres psql -d "$testdb" -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20261001_device_configuration.up.sql" >/dev/null
sudo -u postgres psql -d "$testdb" -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20261001_device_configuration.down.sql" >/dev/null
sudo -u postgres psql -d "$testdb" -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20261001_device_configuration.up.sql" >/dev/null
sudo -u postgres env PYTHONPATH="$release/backend/tracker_py" "$target/.venv/bin/python" "$release/scripts/tracker-configuration-pg-check.py" "$testdb"

odootest=TRACKER_MOBILITY_ODOO_QA_$stamp
sudo -u postgres createdb -O dev_odoo18 "$odootest"
sudo cat "$backup/LAB_TAREAS.dump" | sudo -u postgres pg_restore --no-owner --role=dev_odoo18 -d "$odootest"
mkdir "$release/qa-addons"
ln -s "$release/step_tracker_portal" "$release/qa-addons/step_tracker_portal"
sudo -u odoo env PYTHONPATH=/opt/odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf -d "$odootest" --addons-path="$release/qa-addons,/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/opt/dev_odoo18/odoo_agriculture" -u step_tracker_portal --stop-after-init --no-http --max-cron-threads=0 --logfile=/tmp/tracker-mobility-qa.log
echo "ODOO_MIGRATION_REHEARSAL_OK=$odootest"

# The migration is additive; no existing position or session table changes.
sudo -u postgres psql -d tracker_steps -v ON_ERROR_STOP=1 -f "$release/backend/tracker_py/migrations/20261001_device_configuration.up.sql" >/dev/null
sudo -u postgres psql -d tracker_steps -v ON_ERROR_STOP=1 -c 'GRANT ALL ON gps_device_registrations TO fcaror;' >/dev/null
for file in app/main.py app/models/fleet.py app/routers/fleet.py app/routers/fleet_configuration.py requirements.txt scripts/assign_gps.py; do
 sudo install -o fernandocaro1198_gmail_com -m 644 "$release/backend/tracker_py/$file" "$target/$file"
done
sudo -u fernandocaro1198_gmail_com "$target/.venv/bin/pip" install tzdata==2026.4
sudo systemctl restart tracker-steps-api.service
for attempt in $(seq 1 20); do
 if curl -fsS http://127.0.0.1:8000/health >/dev/null; then break; fi
 sleep 1
done
curl -fsS http://127.0.0.1:8000/openapi.json | python3 -c 'import json,sys; assert "/v1/configuration" in json.load(sys.stdin)["paths"]; print("CONFIGURATION_API_OK")'

deploy_odoo() {
 local db=$1 service=$2 user=$3 config=$4 addons=$5 port=$6 host=$7
 sudo systemctl stop "$service"
 sudo rsync -a "$release/step_tracker_portal/" "$addons/step_tracker_portal/"
 sudo chown -R "$user" "$addons/step_tracker_portal"
 if ! sudo -u "$user" env PYTHONPATH=/opt/odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin -c "$config" -d "$db" -u step_tracker_portal --stop-after-init --no-http --max-cron-threads=0 --logfile="/tmp/tracker-mobility-$db.log"; then
   sudo systemctl start "$service"
   echo "ODOO_UPDATE_FAILED=$db" >&2
   return 1
 fi
 sudo systemctl start "$service"
 for attempt in $(seq 1 40); do
   if curl -fsS -H "Host: $host" "http://127.0.0.1:$port/web/login" >/dev/null; then break; fi
   sleep 1
 done
 curl -fsS -H "Host: $host" "http://127.0.0.1:$port/web/login" >/dev/null
 echo "ODOO_UPDATED=$db"
}
deploy_odoo LAB_TAREAS odoo18-dev.service odoo /etc/dev_odoo18.conf /opt/dev_odoo18/odoo_agriculture 8075 desarrollo.stepsapp.cl
deploy_odoo STEPS_DEMO odoo18-demo.service demo_odoo18 /etc/demo_odoo18.conf /opt/demo_odoo18/odoo_agriculture 8080 demo.stepsapp.cl
deploy_odoo CERRO_EL_PLOMO odoo18-cerroelplomo.service cerro_odoo18 /etc/odoo18-cerroelplomo.conf /opt/cerroelplomo_odoo18/steps_addons 8082 cerroelplomo.stepsapp.cl
sudo rsync -a --delete --chown=root:odoo dist/ /var/www/web_tracker_portal/
sudo nginx -t
sudo systemctl reload nginx
expected=$(grep -o 'assets/index-[^" ]*\.js' /var/www/web_tracker_portal/index.html)
expected_hash=$(sha256sum "/var/www/web_tracker_portal/$expected" | cut -d' ' -f1)
for host in desarrollo.stepsapp.cl demo.stepsapp.cl cerroelplomo.stepsapp.cl; do
 actual=$(curl -fsS "https://$host/web_tracker/" | grep -o 'assets/index-[^" ]*\.js')
 test "$actual" = "$expected"
 actual_hash=$(curl -fsS "https://$host/web_tracker/$actual" | sha256sum | cut -d' ' -f1)
 test "$actual_hash" = "$expected_hash"
 echo "VERIFIED=$host/$actual SHA256=$actual_hash"
done
sudo systemctl start steps-tracker-signal.service
sudo systemctl is-active tracker-steps-api.service odoo18-dev.service odoo18-demo.service odoo18-cerroelplomo.service steps-tracker-signal.timer
# Only ephemeral QA clones created by this exact run are removed.
[[ "$testdb" == TRACKER_CONFIG_QA_* ]] && sudo -u postgres dropdb "$testdb"
[[ "$odootest" == TRACKER_MOBILITY_ODOO_QA_* ]] && sudo -u postgres dropdb "$odootest"
echo "RELEASE=$(git rev-parse HEAD) BACKUP=$backup"
