#!/usr/bin/env bash
set -u

echo '=== SERVICE DEFINITIONS ==='
for service_name in odoo18-dev.service odoo18-demo.service odoo18-demo-sys.service; do
    echo "--- $service_name"
    sudo systemctl show "$service_name" -p User -p Group -p ExecStart -p FragmentPath -p Result -p ExecMainStatus --no-pager
done

echo '=== SAFE CONFIG PATHS ==='
for config_path in /etc/dev_odoo18.conf /etc/demo_odoo18.conf /etc/odoo18-demo-sys.conf; do
    echo "--- $config_path"
    sudo grep -E '^(addons_path|data_dir|db_name|dbfilter|http_port|xmlrpc_port|logfile)' "$config_path" || true
done

echo '=== DEV FAILURE LOG ==='
sudo journalctl -u odoo18-dev.service --since '2026-08-23 04:45:00 UTC' --no-pager -n 220

echo '=== ADDON ROOTS ==='
for code_base in \
    /opt/dev_odoo18/odoo_agriculture \
    /opt/demo_odoo18/odoo_agriculture \
    /opt/demosys_odoo18/odoo_agriculture \
    /opt/odoo18/custom_addons \
    /opt/fernando_odoo18/custom_addons; do
    if sudo test -d "$code_base"; then
        echo "--- $code_base"
        sudo find "$code_base" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | grep -E '^(step_|hr_|l10n_cl)' | sort | head -200
    fi
done

echo '=== EFFECTIVE MODULE HASHES ==='
for code_base in \
    /opt/dev_odoo18/odoo_agriculture \
    /opt/demo_odoo18/odoo_agriculture \
    /opt/demosys_odoo18/odoo_agriculture \
    /opt/odoo18/custom_addons \
    /opt/fernando_odoo18/custom_addons; do
    [ -d "$code_base" ] || continue
    echo "--- $code_base"
    for module_name in step_hr_remuneration_book step_colaciones step_demo_homepage step_agricultural_branding; do
        if sudo test -d "$code_base/$module_name"; then
            module_hash=$(sudo find "$code_base/$module_name" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 | sort -z | sudo xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
            file_count=$(sudo find "$code_base/$module_name" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' | wc -l)
            manifest_version=$(sudo sed -nE 's/.*["'"']version["'"']:[[:space:]]*["'"']([^"'"']+)["'"'].*/\1/p' "$code_base/$module_name/__manifest__.py" | head -1)
            printf '%s|%s|%s|%s\n' "$module_name" "$manifest_version" "$module_hash" "$file_count"
        fi
    done
done
