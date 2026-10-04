#!/usr/bin/env bash
set -euo pipefail
qa=T40_QA_$(date -u +%Y%m%dT%H%M%SZ)
echo "$qa" > /tmp/t40_qa_db_name
sudo -u postgres createdb -O dev_odoo18 "$qa"
sudo -u postgres pg_dump -Fc LAB_TAREAS | sudo -u postgres pg_restore \
  -d "$qa" --no-owner --role=dev_odoo18
sudo mkdir -p /tmp/t40_addons
sudo tar -xzf /tmp/step_inventory_packing.tar.gz -C /tmp/t40_addons
sudo chown -R dev_odoo18:dev_odoo18 /tmp/t40_addons
sudo -u dev_odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf -d "$qa" \
  --addons-path=/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/opt/dev_odoo18/odoo_agriculture,/tmp/t40_addons \
  -i step_inventory_packing --test-enable --test-tags /step_inventory_packing \
  --stop-after-init --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=18094 \
  --logfile=/tmp/t40_qa_install.log
echo "QA_DB=$qa"
sudo grep -E 'Starting TestFruitOperations|post-tests|failed|error.s. of|Module step_inventory_packing loaded' /tmp/t40_qa_install.log | tail -n 20
