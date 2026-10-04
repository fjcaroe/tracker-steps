#!/usr/bin/env bash
set -euo pipefail

case "$1" in
  dev) db=LAB_TAREAS; run_user=odoo; service=odoo18-dev; config=/etc/dev_odoo18.conf; addon_dir=/opt/dev_odoo18/odoo_agriculture; data_dir=/opt/dev_odoo18/.local/share/Odoo; port=8075 ;;
  demo) db=STEPS_DEMO; run_user=demo_odoo18; service=odoo18-demo; config=/etc/demo_odoo18.conf; addon_dir=/opt/demo_odoo18/odoo_agriculture; data_dir=/opt/demo_odoo18/.local/share/Odoo; port=8080 ;;
  cerro) db=CERRO_EL_PLOMO; run_user=cerro_odoo18; service=odoo18-cerroelplomo; config=/etc/odoo18-cerroelplomo.conf; addon_dir=/opt/cerroelplomo_odoo18/steps_addons; data_dir=/opt/cerroelplomo_odoo18/.local/share/Odoo; port=8082 ;;
  demosys) db=STEPS_DEMO_SYS; run_user=demosys_odoo18; service=odoo18-demo-sys; config=/etc/odoo18-demo-sys.conf; addon_dir=/opt/demosys_odoo18/odoo_agriculture; data_dir=/opt/demosys_odoo18/.local/share/Odoo; port=8090 ;;
  *) echo 'usage: deploy_t35_producers.sh dev|demo|cerro|demosys' >&2; exit 2 ;;
esac

archive=/tmp/t35_modules_20260928.tar.gz
backup_dir="/opt/steps_backups/t35_producers_20260928_${1}_$(date -u +%H%M%S)"
stage_dir="/tmp/t35_producers_deploy_${1}_20260928"
test -f "$archive"
test -d "$addon_dir/step_export"
test -d "$addon_dir/step_packing"
test ! -e "$addon_dir/step_producers"
test "$(systemctl is-active "$service")" = active
mkdir -p "$backup_dir" "$stage_dir"
tar -xzf "$archive" -C "$stage_dir"
test -f "$stage_dir/step_export/__manifest__.py"
test -f "$stage_dir/step_packing/__manifest__.py"
test -f "$stage_dir/step_producers/__manifest__.py"

sudo -u postgres pg_dump -Fc "$db" > "$backup_dir/$db.dump"
tar -czf "$backup_dir/filestore.tar.gz" -C "$data_dir/filestore" "$db"
tar -czf "$backup_dir/addons.tar.gz" -C "$addon_dir" step_export step_packing
sha256sum "$archive" "$backup_dir/$db.dump" "$backup_dir/filestore.tar.gz" "$backup_dir/addons.tar.gz" > "$backup_dir/SHA256SUMS"
touch "$backup_dir/update.log"
chown "$run_user:$run_user" "$backup_dir/update.log"
echo "BACKUP=$backup_dir"

stopped=0
restore_service() {
  if [ "$stopped" = 1 ]; then systemctl start "$service" || true; fi
}
trap restore_service EXIT
systemctl stop "$service"
stopped=1
for module in step_export step_packing step_producers; do
  mkdir -p "$addon_dir/$module"
  rsync -a --delete "$stage_dir/$module/" "$addon_dir/$module/"
  chown -R "$run_user:$run_user" "$addon_dir/$module"
done

cd /opt/odoo18
sudo -u "$run_user" /usr/bin/python3.10 ./odoo-bin \
  -c "$config" -d "$db" \
  -u step_packing,step_export -i step_producers \
  --stop-after-init --no-http \
  --logfile="$backup_dir/update.log"
systemctl start "$service"
stopped=0
systemctl is-active "$service"
sudo -u postgres psql -d "$db" -Atqc "SELECT name,latest_version,state FROM ir_module_module WHERE name IN ('step_packing','step_export','step_producers') ORDER BY name"
for attempt in $(seq 1 15); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${port}/web/login"; then
    echo HTTP=200
    break
  fi
  if [ "$attempt" = 15 ]; then echo 'HTTP check failed' >&2; exit 1; fi
  sleep 2
done
echo "DEPLOYED=$db"
