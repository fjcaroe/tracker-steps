set -euo pipefail
expected=$(grep -o 'assets/index-[^" ]*\.js' /var/www/web_tracker_portal/index.html)
for host in desarrollo.stepsapp.cl demo.stepsapp.cl cerroelplomo.stepsapp.cl; do
 actual=$(curl -fsS "https://$host/web_tracker/" | grep -o 'assets/index-[^" ]*\.js')
 test "$actual" = "$expected"
 served=$(curl -fsS "https://$host/web_tracker/$actual" | sha256sum | cut -d' ' -f1)
 disk=$(sha256sum "/var/www/web_tracker_portal/$actual" | cut -d' ' -f1)
 test "$served" = "$disk"
 echo "VERIFIED $host $actual $served"
done
sudo systemctl is-active tracker-steps-api.service teltonika-ingest.service odoo18-dev.service odoo18-demo.service odoo18-cerroelplomo.service steps-tracker-signal.timer
sudo systemctl show steps-tracker-signal.service -p Result
