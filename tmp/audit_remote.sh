#!/usr/bin/env bash
set -eu

echo '=== TIME AND ACTIVE DEPLOYS ==='
date -Is
ps -eo pid,lstart,cmd | grep -E 'odoo-bin.*(-u|--update)|rsync|scp ' | grep -v grep || true

echo '=== SERVICES ==='
for service_name in odoo18-dev.service odoo18-demo.service odoo18-demo-sys.service; do
    printf '%s ' "$service_name"
    systemctl is-active "$service_name" || true
    systemctl show "$service_name" -p ActiveEnterTimestamp -p ExecMainStartTimestamp --no-pager
done

echo '=== HTTP ==='
for url in \
    https://desarrollo.stepsapp.cl/web/login \
    https://demo.stepsapp.cl/web/login \
    https://demo-sys.stepsapp.cl/web/login; do
    curl -LksS -o /dev/null -w '%{url_effective} %{http_code} %{time_total}\n' "$url" || true
done

echo '=== RELEVANT MODULE DB STATE ==='
sudo -u postgres psql -Atqc "SELECT datname FROM pg_database WHERE datname IN ('LAB_TAREAS','STEPS_DEMO','STEPS_DEMO_SYS') ORDER BY datname"
for db_name in LAB_TAREAS STEPS_DEMO STEPS_DEMO_SYS; do
    echo "--- $db_name"
    sudo -u postgres psql -d "$db_name" -AtF '|' -c "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('step_hr_remuneration_book','step_colaciones','step_demo_homepage','step_agricultural_branding') ORDER BY name;" || true
done

echo '=== CODE HASHES ==='
for code_base in \
    /opt/dev_odoo18/odoo_agriculture \
    /opt/demo_odoo18/odoo_agriculture \
    /opt/demosys_odoo18/odoo_agriculture; do
    echo "--- $code_base"
    for module_name in step_hr_remuneration_book step_colaciones step_demo_homepage step_agricultural_branding; do
        if [ -d "$code_base/$module_name" ]; then
            module_hash=$(find "$code_base/$module_name" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
            file_count=$(find "$code_base/$module_name" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' | wc -l)
            printf '%s|%s|%s\n' "$module_name" "$module_hash" "$file_count"
        else
            printf '%s|MISSING|0\n' "$module_name"
        fi
    done
done
