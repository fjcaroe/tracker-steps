#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/environments.sh" "${1:?Environment required}"
sudo /usr/bin/python3.10 "$(dirname "$0")/verify_release.py" /tmp/steps_assistant_release.tar.gz "$TARGET"
RUN_USER=$(sudo systemctl show "$SERVICE" -p User --value)
PYTHON=/usr/bin/python3.10
if [[ "$1" = produccion || "$1" = sys-produccion ]]; then PYTHON=/opt/odoo18/venv/bin/python; fi
sudo -u "$RUN_USER" "$PYTHON" /opt/odoo18/odoo-bin shell -c "$CONFIG" -d "$DB" \
  --no-http --logfile="/tmp/steps-assistant-$1-smoke.log" < "$(dirname "$0")/smoke_business.py"
