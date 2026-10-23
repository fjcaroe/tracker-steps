#!/usr/bin/env bash
set -euo pipefail
qa=$(cat /tmp/t40_qa_db_name)
sudo tar -xzf /tmp/step_inventory_packing.tar.gz -C /tmp/t40_addons
sudo chown -R odoo:odoo /tmp/t40_addons
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf -d "$qa" \
  --addons-path=/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/opt/dev_odoo18/odoo_agriculture,/tmp/t40_addons \
  -u step_inventory_packing --test-enable --test-tags /step_inventory_packing \
  --stop-after-init --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=18094 \
  --logfile=/tmp/t40_qa_install.log
echo "QA_DB=$qa"
sudo grep -E 'Starting TestFruitOperations|post-tests|failed|error.s. of|Module step_inventory_packing loaded' /tmp/t40_qa_install.log | tail -n 20
