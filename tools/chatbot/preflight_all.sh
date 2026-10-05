#!/usr/bin/env bash
set -euo pipefail
for ENV in desarrollo demo demo-sys cerroelplomo produccion; do
  source "$(dirname "$0")/environments.sh" "$ENV"
  printf '\nENVIRONMENT=%s DB=%s TARGET=%s\n' "$ENV" "$DB" "$TARGET"
  sudo systemctl is-active "$SERVICE"
  sudo systemctl show "$SERVICE" -p User -p WorkingDirectory -p ExecStart
  sudo test -f "$CONFIG" && sudo test -d "$TARGET"
  sudo -u postgres psql -d "$DB" -Atc "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('account','sale','purchase','stock','mrp','project','step_colaciones','step_account_treasury','knowledge','step_support_assistant','step_support_assistant_knowledge') ORDER BY name;"
  sudo -u postgres psql -d "$DB" -Atc "SELECT COUNT(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');"
  curl --silent --output /dev/null --connect-timeout 5 --max-time 15 --write-out 'HTTP=%{http_code}\n' "$URL/web/login"
done
