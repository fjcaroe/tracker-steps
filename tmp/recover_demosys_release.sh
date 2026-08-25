#!/usr/bin/env bash
set -euo pipefail

stage="/tmp/steps-homologated-20260823-0505-clt"
code_base="/opt/demosys_odoo18/odoo_agriculture"
service_name="odoo18-demo-sys.service"
run_user="demosys_odoo18"
config_path="/etc/odoo18-demo-sys.conf"
db_name="STEPS_DEMO_SYS"

for module_name in \
    step_hr_remuneration_book \
    step_colaciones \
    step_demo_homepage \
    step_agricultural_branding; do
    sudo mkdir -p "$code_base/$module_name"
    sudo rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
        "$stage/$module_name/" "$code_base/$module_name/"
    sudo chown -R "$run_user:$run_user" "$code_base/$module_name"
done

sudo systemctl stop "$service_name"
sudo -u "$run_user" /usr/bin/python3.10 /opt/odoo18/odoo-bin \
    -c "$config_path" -d "$db_name" --stop-after-init \
    -i step_colaciones \
    -u step_hr_remuneration_book,step_demo_homepage,step_agricultural_branding
sudo systemctl start "$service_name"
sudo systemctl is-active --quiet "$service_name"

echo 'DEMOSYS_PRIMARY_MODULES_COMPLETE'
