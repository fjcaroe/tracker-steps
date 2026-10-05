#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/environments.sh" "${1:?Environment required}"
RUN_USER=$(sudo systemctl show "$SERVICE" -p User --value)
PYTHON=/usr/bin/python3.10
if test "$1" = produccion; then PYTHON=/opt/odoo18/venv/bin/python; fi
sudo -u "$RUN_USER" "$PYTHON" /opt/odoo18/odoo-bin shell -c "$CONFIG" -d "$DB" \
  --no-http --logfile="/tmp/steps-assistant-$1-smoke.log" < "$(dirname "$0")/smoke_business.py"
