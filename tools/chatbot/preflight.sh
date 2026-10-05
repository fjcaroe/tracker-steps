#!/usr/bin/env bash
set -euo pipefail
# Read-only environment inventory. Never print Odoo configuration or environment values.
systemctl is-active odoo18-dev.service
systemctl show odoo18-dev.service -p User -p WorkingDirectory -p ExecStart
test -d /opt/dev_odoo18/odoo_agriculture
test -f /etc/dev_odoo18.conf
sudo -u postgres psql -d LAB_TAREAS -Atc "SELECT name,state FROM ir_module_module WHERE name IN ('base','web','step_colaciones','helpdesk','knowledge','step_support_assistant') ORDER BY name;"
sudo -u postgres psql -d LAB_TAREAS -Atc "SELECT COUNT(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');"
for candidate in /opt/odoo18/odoo-bin /opt/odoo18/odoo/odoo-bin; do
    test ! -f "$candidate" || printf 'ODOO_BIN=%s\n' "$candidate"
done
if sudo test -f /etc/steps/assistant-dev.env; then
    printf 'ASSISTANT_ENV_EXISTS\n'
fi
