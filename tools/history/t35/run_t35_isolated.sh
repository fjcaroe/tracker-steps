#!/usr/bin/env bash
set -euo pipefail

test_db=T35_PRODUCERS_TEST_20260928
test_root=/tmp/t35_producers_test_20260928
if sudo -u postgres psql -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname='${test_db}'" | grep -q 1; then
    echo "Test database already exists; refusing to overwrite it" >&2
    exit 1
fi

sudo -u postgres createdb -O dev_odoo18 "${test_db}"
sudo -u postgres pg_dump -Fc LAB_TAREAS | sudo -u postgres pg_restore -d "${test_db}" --no-owner --no-acl
sudo install -d -o odoo -g odoo -m 700 "${test_root}/addons"
sudo tar -xzf /tmp/t35_producers_modules_20260928.tar.gz -C "${test_root}/addons"
sudo install -d -o odoo -g odoo -m 700 "/opt/dev_odoo18/.local/share/Odoo/filestore/${test_db}"
sudo cp -a /opt/dev_odoo18/.local/share/Odoo/filestore/LAB_TAREAS/. "/opt/dev_odoo18/.local/share/Odoo/filestore/${test_db}/"
sudo chown -R odoo:odoo "/opt/dev_odoo18/.local/share/Odoo/filestore/${test_db}"

cd /opt/odoo18
sudo -u odoo /usr/bin/python3.10 ./odoo-bin \
  -c /etc/dev_odoo18.conf -d "${test_db}" \
  --addons-path="${test_root}/addons,/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/opt/dev_odoo18/odoo_agriculture" \
  -u step_export -i step_producers --test-enable \
  --test-tags /step_export,/step_producers --stop-after-init --no-http \
  --logfile="${test_root}/odoo.log"

sudo grep -E 'Starting Test|tests? passed|FAIL|ERROR|modules loaded|Initiating shutdown' "${test_root}/odoo.log" | tail -n 80
