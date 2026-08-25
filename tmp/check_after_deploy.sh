#!/usr/bin/env bash
set -u

date -Is
for service_name in odoo18-dev.service odoo18-demo.service odoo18-demo-sys.service; do
    echo "--- $service_name"
    systemctl is-active "$service_name" || true
done
echo '=== DEMOSYS LOG ==='
sudo tail -n 320 /var/log/odoo18/odoo-demo-sys.log || true
echo '=== DEMOSYS JOURNAL ==='
sudo journalctl -u odoo18-demo-sys.service --since '2026-08-23 09:10:35 UTC' --no-pager -n 220 || true
