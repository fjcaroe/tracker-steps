#!/usr/bin/env bash
set -u

echo '=== DEV SINCE 09:12 ==='
sudo journalctl -u odoo18-dev.service --since '2026-08-23 09:12:00 UTC' --no-pager \
    | grep -E 'ERROR|CRITICAL|Traceback' | tail -100 || true
echo '=== DEMO SINCE 09:12 ==='
sudo journalctl -u odoo18-demo.service --since '2026-08-23 09:12:00 UTC' --no-pager \
    | grep -E 'ERROR|CRITICAL|Traceback' | tail -100 || true
echo '=== DEMOSYS SINCE 09:14:41 ==='
sudo awk '$1" "$2 >= "2026-08-23 09:14:41"' /var/log/odoo18/odoo-demo-sys.log \
    | grep -E 'ERROR|CRITICAL|Traceback' | tail -100 || true
