#!/usr/bin/env bash
# Despliegue de los módulos puente Tracker ↔ Gastos ↔ Gestión y Costos en DESARROLLO (odoo-new).
#
# Se ejecuta EN el servidor, con los módulos ya copiados a $STAGE (un directorio por módulo):
#   step_tracker_usage  step_expense_tracker  step_management_costs_tracker
#
# No toca módulos existentes: solo agrega directorios nuevos al árbol de Desarrollo, que también leen
# odoo18.service y odoo18-everfruit.service; allí los módulos no están instalados, así que no se cargan.
# Antes de instalar toma un respaldo verificable de la base y comprueba que nadie más la esté actualizando.
set -euo pipefail

STAGE=${STAGE:-/tmp/trkcost/deploy}
ADDONS=/opt/dev_odoo18/odoo_agriculture
DB=LAB_TAREAS
SERVICE=odoo18-dev.service
CONF=/etc/dev_odoo18.conf
PORT=8075
MODULES="step_tracker_usage step_expense_tracker step_management_costs_tracker"
TS=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/backups/trkcost-dev-$TS

echo "== 1. Comprobaciones previas"
for m in $MODULES; do test -f "$STAGE/$m/__manifest__.py" || { echo "falta $STAGE/$m"; exit 1; }; done
if pgrep -af "odoo-bin.*-(i|u) .*-d $DB|odoo-bin.*-d $DB.*-(i|u) " >/dev/null; then
  echo "Hay otra instalación/actualización sobre $DB: se aborta"; exit 1
fi
sudo -u postgres psql -Atc "select name||':'||state||':'||coalesce(latest_version,'') from ir_module_module where name in ('step_tracker_odoo','step_tracker_portal','step_expense_report','step_management_costs','step_hr') order by 1" -d $DB
for s in odoo18.service odoo18-everfruit.service odoo18-demo.service odoo18-sys.service; do
  echo "$s PID=$(systemctl show -p MainPID --value $s) desde=$(systemctl show -p ActiveEnterTimestamp --value $s)"
done

echo "== 2. Respaldo"
sudo mkdir -p "$BACKUP"
sudo chown postgres "$BACKUP"
sudo -u postgres pg_dump -Fc -d $DB -f "$BACKUP/$DB.dump"
sudo -u postgres pg_restore -l "$BACKUP/$DB.dump" >/dev/null
(cd "$BACKUP" && sudo sha256sum $DB.dump | sudo tee SHA256SUMS >/dev/null)
sudo test -s "$BACKUP/$DB.dump" && echo "respaldo: $BACKUP ($(sudo du -h $BACKUP/$DB.dump | cut -f1))"
sudo chown -R root:root "$BACKUP"; sudo chmod 700 "$BACKUP"

echo "== 3. Copia de módulos nuevos"
for m in $MODULES; do
  sudo rsync -a --delete --exclude '__pycache__' "$STAGE/$m/" "$ADDONS/$m/"
  sudo chown -R odoo:odoo "$ADDONS/$m"
done

echo "== 4. Instalación"
sudo systemctl stop $SERVICE
cd /opt/odoo18
set +e
sudo -u odoo /usr/bin/python3.10 ./odoo-bin -c $CONF -d $DB -i step_management_costs_tracker --stop-after-init --no-http \
  --log-level=warn > /tmp/trkcost-install-$TS.log 2>&1
RC=$?
set -e
echo "instalación RC=$RC"
grep -E "ERROR|CRITICAL|Traceback" /tmp/trkcost-install-$TS.log | grep -v "steps_api" | head -20 || true
if [ $RC -ne 0 ]; then
  echo "FALLÓ: se restaura el servicio sin los módulos (la base no quedó modificada de forma parcial si RC!=0 en -i)"
  sudo systemctl start $SERVICE
  exit $RC
fi
sudo systemctl start $SERVICE

echo "== 5. Verificación"
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/web/login || true)
  [ "$code" = "200" ] && break
  sleep 2
done
echo "HTTP /web/login = $code"
systemctl is-active $SERVICE
sudo -u postgres psql -Atc "select name||':'||state||':'||coalesce(latest_version,'') from ir_module_module where name in ('step_tracker_usage','step_expense_tracker','step_management_costs_tracker') order by 1" -d $DB
for s in odoo18.service odoo18-everfruit.service odoo18-demo.service odoo18-sys.service; do
  echo "$s PID=$(systemctl show -p MainPID --value $s) desde=$(systemctl show -p ActiveEnterTimestamp --value $s)"
done
echo "REVERSIÓN: sudo systemctl stop $SERVICE; sudo -u postgres dropdb $DB; sudo -u postgres createdb -O dev_odoo18 $DB;"
echo "           sudo -u postgres pg_restore --no-owner --role=dev_odoo18 -d $DB $BACKUP/$DB.dump; retirar los 3 directorios de $ADDONS; sudo systemctl start $SERVICE"
echo "BACKUP=$BACKUP"
