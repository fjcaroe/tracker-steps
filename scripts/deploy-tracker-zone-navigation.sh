#!/usr/bin/env bash
# Code-only update after polygons: no database migration or Odoo module update.
set -euo pipefail
release=${TRACKER_RELEASE:?Set fresh checkout directory}
target=/opt/fernando_odoo18/apis/backend/tracker_py
base=4d7c9b8
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/backups/tracker-zone-navigation-$stamp
cd "$release"
test -d .git
python3 - "$release" "$target" "$base" <<'PY'
import pathlib,subprocess,sys
release,target,base=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),sys.argv[3]
rel='app/routers/fleet.py'
old=subprocess.check_output(['git','show',base+':backend/tracker_py/'+rel]).decode().replace('\r\n','\n')
new=(release/'backend/tracker_py'/rel).read_text().replace('\r\n','\n')
assert (target/rel).read_text().replace('\r\n','\n') in (old,new),'Unreviewed API drift'
PY
sudo install -d -m 700 "$backup"
sudo cp -a "$target/app/routers/fleet.py" "$backup/fleet.py"
sudo cp -a /var/www/web_tracker_portal "$backup/web_tracker_portal"
echo "BACKUP=$backup"
sudo cp /opt/fernando_odoo18/apis/tracker-steps/.env .env
sudo cp /opt/fernando_odoo18/apis/tracker-steps/.env.production .env.production
sudo chown "$(whoami)" .env .env.production
chmod 600 .env .env.production
trap 'rm -f -- "$release/.env" "$release/.env.production"' EXIT
npm ci --no-audit --no-fund
VITE_ODOO_PORTAL=true npm run build
sudo install -o fernandocaro1198_gmail_com -m 644 backend/tracker_py/app/routers/fleet.py "$target/app/routers/fleet.py"
sudo systemctl restart tracker-steps-api.service
for attempt in $(seq 1 20); do
 if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
 sleep 1
done
if ! curl -fsS http://127.0.0.1:8000/openapi.json | python3 -c 'import json,sys;p=json.load(sys.stdin)["paths"]["/v1/assets/{asset_id}/positions"]["get"]["parameters"];assert {"current_assignment","since"} <= {x["name"] for x in p};print("RECENT_TRAIL_API_OK")'; then
 sudo cp -a "$backup/fleet.py" "$target/app/routers/fleet.py"
 sudo systemctl restart tracker-steps-api.service
 exit 1
fi
sudo rsync -a --delete --chown=root:odoo dist/ /var/www/web_tracker_portal/
sudo nginx -t
sudo systemctl reload nginx
expected=$(grep -o 'assets/index-[^" ]*\.js' dist/index.html)
expected_hash=$(sha256sum "dist/$expected" | cut -d' ' -f1)
for host in desarrollo.stepsapp.cl demo.stepsapp.cl cerroelplomo.stepsapp.cl; do
 actual=$(curl -fsS "https://$host/web_tracker/" | grep -o 'assets/index-[^" ]*\.js')
 test "$actual" = "$expected"
 actual_hash=$(curl -fsS "https://$host/web_tracker/$actual" | sha256sum | cut -d' ' -f1)
 test "$actual_hash" = "$expected_hash"
 echo "VERIFIED=$host/$actual SHA256=$actual_hash"
done
sudo systemctl is-active tracker-steps-api.service odoo18-dev.service odoo18-demo.service odoo18-cerroelplomo.service
echo "RELEASE=$(git rev-parse HEAD) BACKUP=$backup"
