#!/usr/bin/env bash
# Run from a fresh server checkout of codex/steps-movil, with its exact commit as argument.
set -euo pipefail
release=$(pwd)
chmod 755 "$release"
expected=${1:?Pass the reviewed release commit}
test "$(git rev-parse HEAD)" = "$expected"
test "$(git branch --show-current)" = codex/steps-movil
test -z "$(git status --porcelain --untracked-files=no)"
target=/opt/fernando_odoo18/apis/backend/tracker_py
front=/var/www/steps-truck-frontend
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/fernando_odoo18/backups/movil-consolidado-$stamp
qa=TRACKER_MOVIL_QA_$stamp
exec 9>/tmp/steps-movil-deploy.lock
flock -n 9 || { echo 'Another mobile deployment is running' >&2; exit 1; }

# Refuse to overwrite source changes absent from the reviewed branch histories.
python3 - "$release" "$target" > /tmp/movil-delta-$stamp.txt <<'PY'
import pathlib, subprocess, sys
release, target = map(pathlib.Path, sys.argv[1:])
refs = ['origin/codex/steps-movil', 'origin/ticket/46-movil-mejoras',
        'origin/ticket/46-movil-jornada-no-se-pierde', 'origin/ticket/46-movil-jornada-persistente']
for source in sorted((release/'backend/tracker_py/app').rglob('*.py')):
    rel = source.relative_to(release/'backend/tracker_py')
    dest = target/rel
    new = source.read_text().replace('\r\n', '\n')
    actual = dest.read_text().replace('\r\n', '\n') if dest.exists() else None
    if actual == new:
        continue
    known = []
    for ref in refs:
        result = subprocess.run(['git', '-C', str(release), 'show', f'{ref}:backend/tracker_py/{rel.as_posix()}'], capture_output=True)
        if result.returncode == 0:
            known.append(result.stdout.decode().replace('\r\n', '\n'))
    if actual is not None and actual not in known:
        raise SystemExit(f'Unreviewed server source: {rel}')
    print(rel.as_posix())
PY
echo 'REVIEWED_BACKEND_DELTA:'
cat /tmp/movil-delta-$stamp.txt

# Build only the mobile app; its default API URL is public and production-specific.
cd "$release/mobile"
npm ci --no-audit --no-fund
npm test
npm run build
cd "$release"
sudo install -d -m 700 "$backup"
sudo -u postgres pg_dump -Fc tracker_steps | sudo tee "$backup/tracker_steps.dump" >/dev/null
sudo pg_restore --list "$backup/tracker_steps.dump" >/dev/null
sudo cp -a "$target" "$backup/tracker_py"
sudo cp -a "$front" "$front.pre-movil-$stamp"
printf '%s\n' "$expected" | sudo tee "$backup/RELEASE" >/dev/null
echo "BACKUP=$backup FRONT_BACKUP=$front.pre-movil-$stamp"

# Rehearse ORM access on an isolated copy; never use a test client against production data.
sudo -u postgres createdb "$qa"
cleanup() { sudo -u postgres dropdb --if-exists "$qa"; }
trap cleanup EXIT
sudo cat "$backup/tracker_steps.dump" | sudo -u postgres pg_restore --no-owner -d "$qa"
sudo -u postgres env DATABASE_URL="postgresql+psycopg2:///$qa" JWT_SECRET=test-only-secret PYTHONPATH="$release/backend/tracker_py" "$target/.venv/bin/python" - <<'PY'
from sqlalchemy import select
from app.main import app  # Register every related model as production startup does.
from app.db.session import SessionLocal
from app.models.sessions import TrackingSession
from app.models.work_orders import WorkOrder
from app.models.mobile import MobileIncident, MobileExpense, MobileChecklist, MobileDevice, MobileDiagnostic, MobileRoute
with SessionLocal() as db:
    for model in [TrackingSession, WorkOrder, MobileIncident, MobileExpense, MobileChecklist, MobileDevice, MobileDiagnostic, MobileRoute]:
        db.execute(select(model).limit(1)).first()
print('POSTGRES_SCHEMA_REHEARSAL_OK')
PY

rollback() {
  echo 'Restoring prior mobile release after verification failure' >&2
  # Restore only source files changed by this release; keep uploads received since the backup.
  while IFS= read -r file; do
    if sudo test -f "$backup/tracker_py/$file"; then
      sudo cp -a "$backup/tracker_py/$file" "$target/$file"
    else
      sudo rm -- "$target/$file"
    fi
  done < /tmp/movil-delta-$stamp.txt
  sudo systemctl restart tracker-steps-api.service
  sudo rsync -a --delete "$front.pre-movil-$stamp/" "$front/"
  sudo nginx -t && sudo systemctl reload nginx
}
trap 'rollback; cleanup' ERR
while IFS= read -r file; do
  sudo install -D -o fernandocaro1198_gmail_com -m 644 "$release/backend/tracker_py/$file" "$target/$file"
done < /tmp/movil-delta-$stamp.txt
sudo systemctl restart tracker-steps-api.service
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then break; fi
  sleep 1
done
sudo systemctl is-active --quiet tracker-steps-api.service
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/openapi.json | python3 -c 'import json,sys; p=json.load(sys.stdin)["paths"]; assert all(x in p for x in ["/mobile/routes", "/mobile/incidents", "/auth/refresh", "/sessions/my"]); print("MOBILE_API_CONTRACT_OK")'
sudo rsync -a --delete --chown=www-data:www-data "$release/mobile/dist/" "$front/"
sudo nginx -t
sudo systemctl reload nginx
python3 - "$front" <<'PY'
import hashlib, pathlib, re, sys, urllib.request
front = pathlib.Path(sys.argv[1])
index = urllib.request.urlopen('https://stepsapp.cl/truck/').read().decode()
asset = re.search(r'src="\./(assets/index-[^" ]+\.js)"', index).group(1)
assert asset in (front/'index.html').read_text()
actual = hashlib.sha256(urllib.request.urlopen('https://stepsapp.cl/truck/'+asset).read()).hexdigest()
assert actual == hashlib.sha256((front/asset).read_bytes()).hexdigest()
print(f'VERIFIED_JS={asset} SHA256={actual}')
PY
trap - ERR
echo "DEPLOYED_RELEASE=$expected"
