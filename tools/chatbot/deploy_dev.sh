#!/usr/bin/env bash
set -euo pipefail
ARCHIVE=${1:?Code archive required}
EXPECTED_SHA=${2:?SHA256 required}
MODULE=step_support_assistant
BRIDGE=step_support_assistant_knowledge
TARGET=/opt/dev_odoo18/odoo_agriculture
DB=LAB_TAREAS
CONFIG=/etc/dev_odoo18.conf
SERVICE=odoo18-dev.service
test "$(sha256sum "$ARCHIVE" | cut -d ' ' -f 1)" = "$EXPECTED_SHA"
test -d "$TARGET" && test -f "$CONFIG"
sudo systemctl is-active --quiet "$SERVICE"
PENDING=$(sudo -u postgres psql -d "$DB" -Atc "SELECT COUNT(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');")
test "$PENDING" = 0
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/opt/backups/steps-assistant-dev-$STAMP
sudo install -d -m 0700 -o postgres -g postgres "$BACKUP"
sudo -u postgres pg_dump -Fc -d "$DB" -f "$BACKUP/$DB.dump"
sudo chown root:root "$BACKUP"
if sudo test -d "$TARGET/$MODULE"; then
    sudo tar -czf "$BACKUP/$MODULE.before.tar.gz" -C "$TARGET" "$MODULE"
else
    sudo touch "$BACKUP/$MODULE.was_absent"
fi
if sudo test -d "$TARGET/$BRIDGE"; then
    sudo tar -czf "$BACKUP/$BRIDGE.before.tar.gz" -C "$TARGET" "$BRIDGE"
else
    sudo touch "$BACKUP/$BRIDGE.was_absent"
fi
STAGING=$(mktemp -d /tmp/steps-assistant-code.XXXXXX)
tar -xzf "$ARCHIVE" -C "$STAGING" --no-same-owner
sudo install -d -m 0755 "$TARGET/$MODULE"
# No deletion of existing files. Show exactly what will be copied before applying it.
sudo rsync -ani --exclude '__pycache__/' --exclude '*.pyc' "$STAGING/$MODULE/" "$TARGET/$MODULE/"
sudo rsync -a --chown=root:odoo --exclude '__pycache__/' --exclude '*.pyc' "$STAGING/$MODULE/" "$TARGET/$MODULE/"
sudo install -d -m 0755 "$TARGET/$BRIDGE"
sudo rsync -ani --exclude '__pycache__/' --exclude '*.pyc' "$STAGING/$BRIDGE/" "$TARGET/$BRIDGE/"
sudo rsync -a --chown=root:odoo --exclude '__pycache__/' --exclude '*.pyc' "$STAGING/$BRIDGE/" "$TARGET/$BRIDGE/"
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin -c "$CONFIG" -d "$DB" \
    -i "$MODULE,$BRIDGE" -u "$MODULE,$BRIDGE" --workers=0 --max-cron-threads=0 --no-http --stop-after-init \
    --without-demo=all --logfile=/tmp/steps-assistant-dev-install.log
sudo systemctl restart "$SERVICE"
sudo systemctl is-active --quiet "$SERVICE"
curl --fail --silent --output /dev/null https://desarrollo.stepsapp.cl/web/login
sudo -u postgres psql -d "$DB" -Atc "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('$MODULE','$BRIDGE');"
printf 'ASSISTANT_DEV_DEPLOY_OK\nBACKUP=%s\n' "$BACKUP"
