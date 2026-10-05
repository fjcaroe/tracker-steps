#!/usr/bin/env bash
set -euo pipefail
sudo systemctl is-active --quiet odoo18-dev.service
curl --fail --silent --retry 12 --retry-delay 3 --retry-connrefused \
    --connect-timeout 5 --max-time 15 --output /dev/null https://desarrollo.stepsapp.cl/web/login
sudo -u postgres psql -d LAB_TAREAS -Atc "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('step_support_assistant','step_support_assistant_knowledge');"
sudo -u postgres psql -d LAB_TAREAS -Atc "SELECT COUNT(*) FROM step_assistant_article WHERE active AND published;"
sudo find /opt/backups -maxdepth 1 -type d -name 'steps-assistant-dev-*' | sort | tail -n 2
printf 'ASSISTANT_DEV_POSTFLIGHT_OK\n'
