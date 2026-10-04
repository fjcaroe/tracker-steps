#!/usr/bin/env bash
set -euo pipefail
target=/opt/demosys_odoo18/odoo_agriculture/step_hr_previred_simpledigital
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/backups/t39_sii_tax_${stamp}
sudo mkdir -p "$backup"
sudo cp -a "$target" "$backup/module"
sudo -u postgres pg_dump -Fc STEPS_DEMO_SYS | sudo tee "$backup/STEPS_DEMO_SYS.dump" >/dev/null
sudo install -o demosys_odoo18 -g demosys_odoo18 -m 644 /tmp/t39_manifest.py "$target/__manifest__.py"
sudo install -o demosys_odoo18 -g demosys_odoo18 -m 644 /tmp/t39_parser.py "$target/models/impuesto_2da_categoria.py"
sudo install -o demosys_odoo18 -g demosys_odoo18 -m 644 /tmp/t39_test.py "$target/tests/test_impuesto_2da_categoria.py"
sudo systemctl stop odoo18-demo-sys.service
trap 'sudo systemctl start odoo18-demo-sys.service' EXIT
sudo -u demosys_odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/odoo18-demo-sys.conf -d STEPS_DEMO_SYS \
  -u step_hr_previred_simpledigital --test-enable \
  --test-tags /step_hr_previred_simpledigital:TestImpuesto2daCategoria \
  --stop-after-init --logfile /tmp/t39_sii_tax_test.log
echo "BACKUP=$backup"
sudo tail -n 35 /tmp/t39_sii_tax_test.log
