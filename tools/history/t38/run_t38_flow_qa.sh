#!/usr/bin/env bash
set -euo pipefail
qa=$(cat /tmp/t40_qa_db_name)
sudo mkdir -p /tmp/t38_addons
sudo tar -xzf /tmp/step_producer_fruit_flow_t38.tar.gz -C /tmp/t38_addons
sudo tar -xzf /tmp/step_export_producers_t38.tar.gz -C /tmp/t38_addons
sudo chown -R odoo:odoo /tmp/t38_addons
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf -d "$qa" \
  --addons-path=/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/tmp/t38_addons,/opt/dev_odoo18/odoo_agriculture,/tmp/t40_addons \
  -u step_export,step_producers,step_producer_fruit_flow --test-enable --test-tags /step_export,/step_producers,/step_producer_fruit_flow \
  --stop-after-init --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=18095 \
  --logfile=/tmp/t38_flow_qa_install.log
echo "QA_DB=$qa"
sudo grep -E 'Module step_producer_fruit_flow loaded|Starting Test|post-tests|failed|error.s. of|ERROR|Traceback' /tmp/t38_flow_qa_install.log | tail -n 40
