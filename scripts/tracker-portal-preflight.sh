#!/usr/bin/env bash
set -euo pipefail
for db in LAB_TAREAS STEPS_DEMO CERRO_EL_PLOMO; do
  echo "Module preflight: $db"
  sudo -u postgres psql -d "$db" -At -c "SELECT name||':'||state FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');"
done
sudo -u postgres psql -d tracker_steps -At -c "SELECT count(*) FROM pg_stat_activity WHERE datname='tracker_steps';"
df -h / /srv/odoo-data
ps -eo pid,args | grep -E 'odoo-bin.*( -u | -i |--update)' | grep -v grep || true
