#!/usr/bin/env bash
set -eu

validate_one() {
    local run_user="$1"
    local config_path="$2"
    local db_name="$3"
    sudo -u "$run_user" /usr/bin/python3.10 /opt/odoo18/odoo-bin shell \
        -c "$config_path" -d "$db_name" --no-http < /tmp/validate_dashboards.py
}

validate_one odoo /etc/dev_odoo18.conf LAB_TAREAS
validate_one demo_odoo18 /etc/demo_odoo18.conf STEPS_DEMO
validate_one demosys_odoo18 /etc/odoo18-demo-sys.conf STEPS_DEMO_SYS
