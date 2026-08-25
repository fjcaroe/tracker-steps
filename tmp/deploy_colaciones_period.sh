#!/usr/bin/env bash
set -euo pipefail

archive="/tmp/step_colaciones_18.0.2.1.0.tgz"
expected_sha="661b63a813f50893934682c230e6f8737d3ca002375fb1dc26f95ae9c6dc3e68"
stamp="20260823-0520-clt"
stage="/tmp/step-colaciones-${stamp}"
backup_root="/opt/steps_backups/colaciones-periodo-${stamp}"

[ "$(sha256sum "$archive" | cut -d' ' -f1)" = "$expected_sha" ]
mkdir -p "$stage"
tar -xzf "$archive" -C "$stage"
test -f "$stage/step_colaciones/__manifest__.py"

deploy_one() {
    local env_name="$1"
    local service_name="$2"
    local run_user="$3"
    local config_path="$4"
    local db_name="$5"
    local code_base="$6"
    local env_backup="$backup_root/$env_name"

    sudo mkdir -p "$env_backup"
    sudo -u postgres pg_dump -Fc "$db_name" > "/tmp/${db_name}-${stamp}.dump"
    sudo mv "/tmp/${db_name}-${stamp}.dump" "$env_backup/${db_name}-before.dump"
    sudo tar -czf "$env_backup/step_colaciones-before.tgz" -C "$code_base" step_colaciones
    sudo sha256sum "$env_backup"/* | sudo tee "$env_backup/SHA256SUMS" >/dev/null

    sudo systemctl stop "$service_name"
    sudo rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
        "$stage/step_colaciones/" "$code_base/step_colaciones/"
    sudo chown -R "$run_user:$run_user" "$code_base/step_colaciones"
    if ! sudo -u "$run_user" /usr/bin/python3.10 /opt/odoo18/odoo-bin \
        -c "$config_path" -d "$db_name" --stop-after-init -u step_colaciones; then
        sudo tar -xzf "$env_backup/step_colaciones-before.tgz" -C "$code_base"
        sudo chown -R "$run_user:$run_user" "$code_base/step_colaciones"
        sudo systemctl start "$service_name"
        exit 1
    fi
    sudo systemctl start "$service_name"
    sudo systemctl is-active --quiet "$service_name"
    echo "$env_name updated"
}

deploy_one dev odoo18-dev.service odoo /etc/dev_odoo18.conf LAB_TAREAS /opt/dev_odoo18/odoo_agriculture
deploy_one demo odoo18-demo.service demo_odoo18 /etc/demo_odoo18.conf STEPS_DEMO /opt/demo_odoo18/odoo_agriculture
deploy_one demosys odoo18-demo-sys.service demosys_odoo18 /etc/odoo18-demo-sys.conf STEPS_DEMO_SYS /opt/demosys_odoo18/odoo_agriculture

echo "COLACIONES_PERIOD_COMPLETE backup_root=$backup_root"
