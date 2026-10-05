#!/usr/bin/env bash
set -euo pipefail
for ENV in desarrollo demo demo-sys cerroelplomo produccion; do
  source "$(dirname "$0")/environments.sh" "$ENV"
  printf 'ENVIRONMENT=%s\n' "$ENV"
  sudo /usr/bin/python3.10 "$(dirname "$0")/verify_release.py" /tmp/steps_assistant_release.tar.gz "$TARGET"
  sudo systemctl is-active "$SERVICE"
  test "$(sudo -u postgres psql -d "$DB" -Atc "SELECT state FROM ir_module_module WHERE name='step_support_assistant';")" = installed
  test "$(sudo -u postgres psql -d "$DB" -Atc "SELECT COUNT(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');")" = 0
  sudo -u postgres psql -d "$DB" -Atc "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('step_support_assistant','step_support_assistant_knowledge');"
  curl --fail --silent --output /dev/null --connect-timeout 5 --max-time 15 --write-out 'HTTP=%{http_code}\n' "$URL/web/login"
done
printf 'ASSISTANT_ALL_POSTFLIGHT_OK\n'
