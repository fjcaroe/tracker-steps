#!/usr/bin/env bash
set -euo pipefail

case "$1" in
  demo) source_db=STEPS_DEMO; test_db=T35_PRODUCERS_DEMO_V3_20260928; db_user=demo_odoo18; run_user=demo_odoo18; config=/etc/demo_odoo18.conf; base_dir=/opt/demo_odoo18; port=18180 ;;
  cerro) source_db=CERRO_EL_PLOMO; test_db=T35_PRODUCERS_CERRO_TEST_20260928; db_user=cerro_odoo18; run_user=cerro_odoo18; config=/etc/odoo18-cerroelplomo.conf; base_dir=/opt/cerroelplomo_odoo18; port=18182 ;;
  demosys) source_db=STEPS_DEMO_SYS; test_db=T35_PRODUCERS_DEMOSYS_TEST_20260928; db_user=demosys_odoo18; run_user=demosys_odoo18; config=/etc/odoo18-demo-sys.conf; base_dir=/opt/demosys_odoo18; port=18190 ;;
  *) echo 'usage: test_other_envs.sh demo|cerro|demosys' >&2; exit 2 ;;
esac

test_root="/tmp/t35_producers_${1}_test_20260928"
if sudo -u postgres psql -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname='${test_db}'" | grep -q 1; then
  if ! sudo test -d "$test_root/addons/step_export"; then
    echo "Existing test database has no matching addon copy: ${test_db}" >&2
    exit 1
  fi
else
  sudo -u postgres createdb -O "$db_user" "$test_db"
  sudo -u postgres psql -d "$test_db" -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;'
  dump_file="/tmp/${test_db}.dump"
  list_file="/tmp/${test_db}.list"
  sudo -u postgres pg_dump -Fc -f "$dump_file" "$source_db"
  sudo -u postgres pg_restore -l "$dump_file" | sed '/ EXTENSION /d' > "$list_file"
  sudo -u postgres pg_restore -d "$test_db" --no-owner --no-acl --role="$db_user" -L "$list_file" "$dump_file"
  sudo install -d -o "$run_user" -g "$run_user" -m 700 "$test_root/addons"
  sudo tar -xzf /tmp/t35_modules_20260928.tar.gz -C "$test_root/addons"
  sudo install -d -o "$run_user" -g "$run_user" -m 700 "$base_dir/.local/share/Odoo/filestore/$test_db"
  sudo cp -a "$base_dir/.local/share/Odoo/filestore/$source_db/." "$base_dir/.local/share/Odoo/filestore/$test_db/"
  sudo chown -R "$run_user:$run_user" "$base_dir/.local/share/Odoo/filestore/$test_db"
  sudo chown "$run_user:$run_user" "$test_root"
fi

addon_paths="$test_root/addons,/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons"
if [ -d "$base_dir/steps_addons" ]; then addon_paths="$addon_paths,$base_dir/steps_addons"; fi
addon_paths="$addon_paths,$base_dir/odoo_agriculture"

cd /opt/odoo18
sudo -u "$run_user" /usr/bin/python3.10 ./odoo-bin \
  -c "$config" -d "$test_db" \
  --addons-path="$addon_paths" \
  -u step_packing,step_export -i step_producers --test-enable \
  --test-tags /step_export,/step_producers --stop-after-init --http-port="$port" \
  --logfile="$test_root/odoo.log"
sudo grep -E 'Starting Test|tests? passed|FAIL|ERROR|modules loaded|Initiating shutdown' "$test_root/odoo.log" | tail -n 80
