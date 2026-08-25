#!/usr/bin/env bash
set -u

echo 'SERVICES'
for service_name in odoo18-dev.service odoo18-demo.service odoo18-demo-sys.service; do
    printf '%s|' "$service_name"
    systemctl is-active "$service_name" || true
done

echo 'HTTP'
for url in \
    https://desarrollo.stepsapp.cl/ \
    https://demo.stepsapp.cl/ \
    https://demo-sys.stepsapp.cl/; do
    curl -LksS -o /dev/null -w '%{url_effective}|%{http_code}|%{time_total}\n' "$url"
done

echo 'MODULES'
for db_name in LAB_TAREAS STEPS_DEMO STEPS_DEMO_SYS; do
    echo "---$db_name"
    sudo -u postgres psql -d "$db_name" -AtF '|' -c "
        SELECT name, state, COALESCE(latest_version, '')
        FROM ir_module_module
        WHERE name IN (
            'step_hr_contract_lifecycle',
            'step_hr_remuneration_book',
            'step_colaciones',
            'step_demo_homepage',
            'step_agricultural_branding'
        )
        ORDER BY name;
    "
done

echo 'RUNTIME_ERRORS_AFTER_0926'
sudo journalctl -u odoo18-dev.service --since '2026-08-23 09:26:00 UTC' --no-pager | grep -E 'ERROR|CRITICAL|Traceback' | tail -30 || true
sudo journalctl -u odoo18-demo.service --since '2026-08-23 09:26:00 UTC' --no-pager | grep -E 'ERROR|CRITICAL|Traceback' | tail -30 || true
sudo awk '$1" "$2 >= "2026-08-23 09:26:00"' /var/log/odoo18/odoo-demo-sys.log | grep -E 'ERROR|CRITICAL|Traceback' | tail -30 || true
