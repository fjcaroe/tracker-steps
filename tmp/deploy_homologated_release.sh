#!/usr/bin/env bash
set -euo pipefail

release_archive="/tmp/steps_homologated_release_20260823_0505.tgz"
release_sha="07b6c33ab0ab3f18e61a8d541ba4ba1cce16d84ba4453319cb400fe849e02960"
stamp="20260823-0505-clt"
stage="/tmp/steps-homologated-${stamp}"
backup_root="/opt/steps_backups/homologacion-${stamp}"
modules=(
    step_hr_remuneration_book
    step_colaciones
    step_demo_homepage
    step_agricultural_branding
    step_hr_contract_lifecycle
)

actual_sha=$(sha256sum "$release_archive" | cut -d' ' -f1)
if [ "$actual_sha" != "$release_sha" ]; then
    echo "Release checksum mismatch: $actual_sha"
    exit 1
fi

sudo mkdir -p "$stage" "$backup_root"
sudo tar -xzf "$release_archive" -C "$stage"
for module_name in "${modules[@]}"; do
    sudo test -f "$stage/$module_name/__manifest__.py"
done

backup_env() {
    local env_name="$1"
    local db_name="$2"
    local code_base="$3"
    local env_backup="$backup_root/$env_name"
    local present=()

    sudo mkdir -p "$env_backup"
    sudo -u postgres pg_dump -Fc "$db_name" > "/tmp/${db_name}-${stamp}.dump"
    sudo mv "/tmp/${db_name}-${stamp}.dump" "$env_backup/${db_name}-before.dump"
    for module_name in "${modules[@]}"; do
        if sudo test -d "$code_base/$module_name"; then
            present+=("$module_name")
        fi
    done
    if [ "${#present[@]}" -gt 0 ]; then
        sudo tar -czf "$env_backup/addons-before.tgz" -C "$code_base" "${present[@]}"
    fi
    sudo sha256sum "$env_backup"/* | sudo tee "$env_backup/SHA256SUMS" >/dev/null
    echo "Backup verified: $env_backup"
}

restore_code() {
    local env_name="$1"
    local code_base="$2"
    local env_backup="$backup_root/$env_name"
    if sudo test -f "$env_backup/addons-before.tgz"; then
        sudo tar -xzf "$env_backup/addons-before.tgz" -C "$code_base"
    fi
}

sync_release() {
    local code_base="$1"
    local owner="$2"
    for module_name in "${modules[@]}"; do
        sudo mkdir -p "$code_base/$module_name"
        sudo rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
            "$stage/$module_name/" "$code_base/$module_name/"
        sudo chown -R "$owner:$owner" "$code_base/$module_name"
    done
}

run_odoo() {
    local service_name="$1"
    local run_user="$2"
    local config_path="$3"
    local db_name="$4"
    local install_modules="$5"
    local update_modules="$6"
    local command=(
        /usr/bin/python3.10 /opt/odoo18/odoo-bin
        -c "$config_path"
        -d "$db_name"
        --stop-after-init
    )

    if [ -n "$install_modules" ]; then
        command+=( -i "$install_modules" )
    fi
    if [ -n "$update_modules" ]; then
        command+=( -u "$update_modules" )
    fi

    sudo systemctl stop "$service_name"
    if ! sudo -u "$run_user" "${command[@]}"; then
        echo "Odoo update failed for $db_name; restoring previous source."
        return 1
    fi
    sudo systemctl start "$service_name"
    sudo systemctl is-active --quiet "$service_name"
}

deploy_env() {
    local env_name="$1"
    local service_name="$2"
    local run_user="$3"
    local config_path="$4"
    local db_name="$5"
    local code_base="$6"
    local install_modules="$7"
    local update_modules="$8"

    echo "=== Deploying $env_name / $db_name ==="
    sync_release "$code_base" "$run_user"
    if ! run_odoo "$service_name" "$run_user" "$config_path" "$db_name" "$install_modules" "$update_modules"; then
        restore_code "$env_name" "$code_base"
        sudo systemctl start "$service_name"
        sudo systemctl is-active --quiet "$service_name" || true
        exit 1
    fi
}

echo '=== Backing up all environments before writes ==='
backup_env dev LAB_TAREAS /opt/dev_odoo18/odoo_agriculture
backup_env demo STEPS_DEMO /opt/demo_odoo18/odoo_agriculture
backup_env demosys STEPS_DEMO_SYS /opt/demosys_odoo18/odoo_agriculture

deploy_env \
    dev odoo18-dev.service odoo /etc/dev_odoo18.conf LAB_TAREAS \
    /opt/dev_odoo18/odoo_agriculture \
    "" \
    "step_hr_remuneration_book,step_colaciones,step_demo_homepage,step_agricultural_branding,step_hr_contract_lifecycle"

deploy_env \
    demo odoo18-demo.service demo_odoo18 /etc/demo_odoo18.conf STEPS_DEMO \
    /opt/demo_odoo18/odoo_agriculture \
    "step_agricultural_branding,step_demo_homepage" \
    "step_hr_remuneration_book,step_colaciones,step_hr_contract_lifecycle"

deploy_env \
    demosys odoo18-demo-sys.service demosys_odoo18 /etc/odoo18-demo-sys.conf STEPS_DEMO_SYS \
    /opt/demosys_odoo18/odoo_agriculture \
    "step_colaciones,step_demo_homepage,step_hr_contract_lifecycle" \
    "step_hr_remuneration_book,step_agricultural_branding"

echo '=== Final source checksums ==='
for code_base in \
    /opt/dev_odoo18/odoo_agriculture \
    /opt/demo_odoo18/odoo_agriculture \
    /opt/demosys_odoo18/odoo_agriculture; do
    echo "--- $code_base"
    for module_name in "${modules[@]}"; do
        sudo find "$code_base/$module_name" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 \
            | sort -z \
            | sudo xargs -0 sha256sum \
            | sha256sum
    done
done

echo "DEPLOYMENT_COMPLETE backup_root=$backup_root"
