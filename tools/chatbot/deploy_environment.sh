#!/usr/bin/env bash
set -euo pipefail
ENV=${1:?Environment required}
ARCHIVE=${2:?Code archive required}
EXPECTED_SHA=${3:?SHA256 required}
source "$(dirname "$0")/environments.sh" "$ENV"
test "$(sha256sum "$ARCHIVE" | cut -d ' ' -f 1)" = "$EXPECTED_SHA"
sudo test -d "$TARGET" && sudo test -f "$CONFIG"
sudo systemctl is-active --quiet "$SERVICE"
RUN_USER=$(sudo systemctl show "$SERVICE" -p User --value)
test -n "$RUN_USER"
PYTHON=/usr/bin/python3.10
if [[ "$ENV" = produccion || "$ENV" = sys-produccion ]]; then PYTHON=/opt/odoo18/venv/bin/python; fi
sudo -u "$RUN_USER" "$PYTHON" -c 'import requests, sass'
PENDING=$(sudo -u postgres psql -d "$DB" -Atc "SELECT COUNT(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');")
test "$PENDING" = 0
MODULES=step_support_assistant
if sudo -u postgres psql -d "$DB" -Atc "SELECT state FROM ir_module_module WHERE name='knowledge';" | grep -qx installed; then
    MODULES=$MODULES,step_support_assistant_knowledge
fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/opt/backups/steps-assistant-$ENV-$STAMP
sudo install -d -m 0700 -o postgres -g postgres "$BACKUP"
sudo -u postgres pg_dump -Fc -d "$DB" -f "$BACKUP/$DB.dump"
sudo chown root:root "$BACKUP"
for MODULE in step_support_assistant step_support_assistant_knowledge; do
    if sudo test -d "$TARGET/$MODULE"; then
        sudo tar -czf "$BACKUP/$MODULE.before.tar.gz" -C "$TARGET" "$MODULE"
    else
        sudo touch "$BACKUP/$MODULE.was_absent"
    fi
done
STAGING=$(mktemp -d /tmp/steps-assistant-code.XXXXXX)
tar -xzf "$ARCHIVE" -C "$STAGING" --no-same-owner
/usr/bin/python3.10 "$(dirname "$0")/validate_assets.py" "$STAGING"
for MODULE in step_support_assistant step_support_assistant_knowledge; do
    sudo install -d -m 0755 "$TARGET/$MODULE"
    sudo rsync -ani --exclude '__pycache__/' --exclude '*.pyc' "$STAGING/$MODULE/" "$TARGET/$MODULE/"
    sudo rsync -a --chown=root:root --chmod=D755,F644 --exclude '__pycache__/' --exclude '*.pyc' "$STAGING/$MODULE/" "$TARGET/$MODULE/"
done
sudo systemctl stop "$SERVICE"
# Always bring the target service back if an upgrade command fails; backups remain.
trap 'sudo systemctl start "$SERVICE"' EXIT
sudo -u "$RUN_USER" "$PYTHON" /opt/odoo18/odoo-bin -c "$CONFIG" -d "$DB" \
    -i "$MODULES" -u "$MODULES" --workers=0 --max-cron-threads=0 --no-http --stop-after-init \
    --without-demo=all --logfile="/tmp/steps-assistant-$ENV-install-$STAMP.log"
sudo systemctl start "$SERVICE"
trap - EXIT
sudo systemctl is-active --quiet "$SERVICE"
curl --fail --silent --retry 12 --retry-delay 3 --retry-connrefused \
    --connect-timeout 5 --max-time 15 --output /dev/null "$URL/web/login"
sudo -u postgres psql -d "$DB" -Atc "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('step_support_assistant','step_support_assistant_knowledge');"
printf 'ASSISTANT_DEPLOY_OK ENV=%s SHA=%s BACKUP=%s\n' "$ENV" "$EXPECTED_SHA" "$BACKUP"
