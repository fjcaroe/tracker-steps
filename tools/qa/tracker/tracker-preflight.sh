set -eu
sudo systemctl show odoo18-cerroelplomo.service -p User -p ExecStart
sudo grep -E '^(addons_path|db_name|db_user)' /etc/dev_odoo18.conf /etc/demo_odoo18.conf /etc/odoo18-cerroelplomo.conf || true
sudo -u postgres psql -d tracker_steps -c '\dt'
for db in LAB_TAREAS STEPS_DEMO CERRO_EL_PLOMO; do
 echo "$db"
 sudo -u postgres psql -d "$db" -c "SELECT name,state FROM ir_module_module WHERE name IN ('step_hr','step_tracker_odoo');"
 sudo -u postgres psql -d "$db" -c "SELECT id,name FROM res_company;"
done
sudo systemctl show teltonika-ingest.service -p WorkingDirectory -p FragmentPath
