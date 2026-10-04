#!/usr/bin/env bash
set -euo pipefail
test_root=/tmp/t35_producers_test_20260928
sudo chown odoo:odoo "${test_root}"
cd /opt/odoo18
sudo -u odoo /usr/bin/python3.10 ./odoo-bin \
  -c /etc/dev_odoo18.conf -d T35_PRODUCERS_TEST_20260928 \
  --addons-path="${test_root}/addons,/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/opt/dev_odoo18/odoo_agriculture" \
  -u step_export -i step_producers --test-enable \
  --test-tags /step_export,/step_producers --stop-after-init --http-port=18075 \
  --logfile="${test_root}/odoo.log"
sudo grep -E 'Starting Test|tests? passed|FAIL|ERROR|modules loaded|Initiating shutdown' "${test_root}/odoo.log" | tail -n 80
