#!/usr/bin/env bash
set -euo pipefail

test_dbs=(
  T35_PRODUCERS_TEST_20260928
  T35_PRODUCERS_DEMO_TEST_20260928
  T35_PRODUCERS_DEMO_V2_20260928
  T35_PRODUCERS_DEMO_V3_20260928
  T35_PRODUCERS_CERRO_TEST_20260928
  T35_PRODUCERS_DEMOSYS_TEST_20260928
)

for db in "${test_dbs[@]}"; do
  case "$db" in T35_PRODUCERS_*_20260928) ;; *) echo "Unexpected test DB: $db" >&2; exit 1;; esac
  sudo -u postgres dropdb --if-exists "$db"
  echo "Dropped $db"
done

test_filestores=(
  /opt/dev_odoo18/.local/share/Odoo/filestore/T35_PRODUCERS_TEST_20260928
  /opt/demo_odoo18/.local/share/Odoo/filestore/T35_PRODUCERS_DEMO_TEST_20260928
  /opt/demo_odoo18/.local/share/Odoo/filestore/T35_PRODUCERS_DEMO_V2_20260928
  /opt/demo_odoo18/.local/share/Odoo/filestore/T35_PRODUCERS_DEMO_V3_20260928
  /opt/cerroelplomo_odoo18/.local/share/Odoo/filestore/T35_PRODUCERS_CERRO_TEST_20260928
  /opt/demosys_odoo18/.local/share/Odoo/filestore/T35_PRODUCERS_DEMOSYS_TEST_20260928
)
for path in "${test_filestores[@]}"; do
  case "$path" in /opt/*/filestore/T35_PRODUCERS_*_20260928) ;; *) echo "Unexpected filestore: $path" >&2; exit 1;; esac
  if [ -d "$path" ]; then rm -rf -- "$path"; echo "Removed $path"; fi
done
