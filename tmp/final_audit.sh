#!/usr/bin/env bash
set -u

modules=(
    step_hr_remuneration_book
    step_colaciones
    step_demo_homepage
    step_agricultural_branding
    step_hr_contract_lifecycle
)

echo '=== SERVICES AND HTTP ==='
for service_name in odoo18-dev.service odoo18-demo.service odoo18-demo-sys.service; do
    printf '%s|' "$service_name"
    systemctl is-active "$service_name" || true
done
for url in \
    https://desarrollo.stepsapp.cl/web/login \
    https://demo.stepsapp.cl/web/login \
    https://demo-sys.stepsapp.cl/web/login; do
    curl -LksS -o /dev/null -w '%{url_effective}|%{http_code}|%{time_total}\n' "$url" || true
done

echo '=== DATABASE MODULE STATE ==='
for db_name in LAB_TAREAS STEPS_DEMO STEPS_DEMO_SYS; do
    echo "--- $db_name"
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

echo '=== SOURCE HASHES ==='
for code_base in \
    /opt/dev_odoo18/odoo_agriculture \
    /opt/demo_odoo18/odoo_agriculture \
    /opt/demosys_odoo18/odoo_agriculture; do
    echo "--- $code_base"
    for module_name in "${modules[@]}"; do
        if sudo test -d "$code_base/$module_name"; then
            hash_value=$(
                sudo find "$code_base/$module_name" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -printf '%P\0' \
                    | sort -z \
                    | while IFS= read -r -d '' relative_path; do
                        printf '%s\0' "$relative_path"
                        sudo cat "$code_base/$module_name/$relative_path"
                        printf '\0'
                    done \
                    | sha256sum \
                    | cut -d' ' -f1
            )
            printf '%s|%s\n' "$module_name" "$hash_value"
        else
            printf '%s|MISSING\n' "$module_name"
        fi
    done
done

echo '=== RECENT ERRORS ==='
for service_name in odoo18-dev.service odoo18-demo.service; do
    echo "--- $service_name"
    sudo journalctl -u "$service_name" --since '2026-08-23 09:09:40 UTC' --no-pager \
        | grep -E 'ERROR|CRITICAL|Traceback' | tail -40 || true
done
echo '--- odoo18-demo-sys.service log after successful recovery'
sudo grep -E 'ERROR|CRITICAL|Traceback' /var/log/odoo18/odoo-demo-sys.log \
    | tail -40 || true

echo '=== BACKUPS ==='
sudo find /opt/steps_backups/homologacion-20260823-0505-clt -maxdepth 2 -type f \
    -printf '%p|%s bytes\n' | sort
