#!/usr/bin/env bash
# Run on odoo-new after copying the archive; deliberately limited to dev/demo.
set -euo pipefail
label=${1:?Usage: deploy_home_commercial.sh dev|demo ARCHIVE_SHA256}
expected=${2:?Archive SHA-256 required}
archive=/tmp/steps-home-commercial-18.0.2.5.0.tar.gz
case "$label" in
  dev) db=LAB_TAREAS; service=odoo18-dev.service; run_user=odoo;
       config=/etc/dev_odoo18.conf; addons=/opt/dev_odoo18/homepage_addons;
       current=/opt/dev_odoo18/odoo_agriculture; port=8075; host=desarrollo.stepsapp.cl ;;
  demo) db=STEPS_DEMO; service=odoo18-demo.service; run_user=demo_odoo18;
        config=/etc/demo_odoo18.conf; addons=/opt/demo_odoo18/odoo_agriculture;
        current=$addons; port=8080; host=demo.stepsapp.cl ;;
  *) echo 'Only dev and demo are allowed' >&2; exit 2 ;;
esac
echo "$expected  $archive" | sha256sum -c -
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/steps_backups/home-commercial-$label-$stamp
stage=$(mktemp -d /tmp/steps-home-commercial.XXXXXX)
stopped=0
cleanup() {
  if [ "$stopped" = 1 ]; then sudo -n systemctl start "$service" || true; fi
  # Preserve staging and logs for diagnosis. No unrelated paths are removed.
}
trap cleanup EXIT
tar -xzf "$archive" -C "$stage"
test -f "$stage/step_demo_homepage/static/src/scss/commercial.scss"
python3 - "$stage" <<'PY'
from pathlib import Path
from lxml import etree
import ast, sys
root = Path(sys.argv[1]) / 'step_demo_homepage'
assert ast.literal_eval((root / '__manifest__.py').read_text())['version'] == '18.0.2.5.0'
tree = etree.parse(str(root / 'views/homepage.xml'))
assert tree.xpath('//*[@data-commercial-version="2026.10"]')
assert len(tree.xpath('//article[@class="steps-product"]')) == 20
PY
sudo -n systemctl is-active --quiet "$service"
sudo -n -u postgres psql -At -d "$db" -c "SELECT state FROM ir_module_module WHERE name='step_demo_homepage'" | grep -qx installed
sudo -n install -d -m 0750 "$backup"
sudo -n cp -a "$config" "$backup/odoo.conf.before"
if [ -d "$addons/step_demo_homepage" ]; then current=$addons; fi
sudo -n tar -czf "$backup/module.before.tar.gz" -C "$current" step_demo_homepage
# Production still reads the original shared directory. Its files must not change.
sudo -n find /opt/dev_odoo18/odoo_agriculture/step_demo_homepage -type f ! -path '*/__pycache__/*' -exec sha256sum {} + | sort > "$stage/production-files.before"
curl -fsS https://stepsapp.cl/ -o "$stage/production.before.html"
sudo -n systemctl stop "$service"
stopped=1
sudo -n -u postgres pg_dump -Fc --lock-wait-timeout=15000 -d "$db" -f "/tmp/home-commercial-$db-$stamp.dump"
sudo -n mv "/tmp/home-commercial-$db-$stamp.dump" "$backup/database.before.dump"
sudo -n install -d -m 0755 "$addons"
if [ "$label" = dev ]; then
  sudo -n python3 - "$config" "$addons" <<'PY'
from pathlib import Path
import sys
p, addons = Path(sys.argv[1]), sys.argv[2]
lines = p.read_text().splitlines()
matches = [i for i, line in enumerate(lines) if line.strip().startswith('addons_path') and '=' in line]
assert len(matches) == 1
i = matches[0]
paths = [v.strip() for v in lines[i].split('=', 1)[1].split(',')]
paths = [addons] + [v for v in paths if v != addons]
lines[i] = 'addons_path = ' + ','.join(paths)
p.write_text('\n'.join(lines) + '\n')
PY
fi
sudo -n rsync -a --delete "$stage/step_demo_homepage/" "$addons/step_demo_homepage/"
sudo -n chown -R "$run_user:$run_user" "$addons/step_demo_homepage"
log=/tmp/home-commercial-$label-$stamp.log
if ! sudo -n -u "$run_user" /usr/bin/python3.10 /opt/odoo18/odoo-bin \
    -c "$config" -d "$db" -u step_demo_homepage --stop-after-init --no-http \
    --logfile="$log" >"$stage/upgrade.stdout" 2>&1; then
  sudo -n cp "$log" "$backup/upgrade.failed.log"
  sudo -n cp -a "$backup/odoo.conf.before" "$config"
  sudo -n tar -xzf "$backup/module.before.tar.gz" -C "$current"
  echo "Upgrade failed; code/config restored. Backup: $backup" >&2
  tail -80 "$log"
  exit 1
fi
sudo -n cp "$log" "$backup/upgrade.log"
sudo -n systemctl start "$service"
stopped=0
sudo -n systemctl is-active --quiet "$service"
curl --fail --silent --show-error --retry 20 --retry-connrefused --retry-delay 1 \
  -H "Host: $host" "http://127.0.0.1:$port/" -o "$stage/rendered.html"
python3 - "$stage/rendered.html" "$port" "$host" <<'PY'
from pathlib import Path
from lxml import html
from urllib.request import Request, urlopen
import sys
page = html.fromstring(Path(sys.argv[1]).read_bytes())
assert len(page.xpath('//h1')) == 1
assert page.xpath('//*[@data-commercial-version="2026.10"]')
assert len(page.xpath('//article[@class="steps-product"]')) == 20
assert len(page.xpath('//*[@data-plan]')) == 3
assert len(page.xpath('//*[@id="preguntas"]//details')) == 7
assert len(page.xpath('//*[@data-app]')) == 5
styles = page.xpath('//link[@rel="stylesheet"]/@href')
css = ''
for path in styles:
    if path.startswith('/web/assets/'):
        req = Request('http://127.0.0.1:' + sys.argv[2] + path, headers={'Host': sys.argv[3]})
        with urlopen(req, timeout=90) as response:
            css += response.read().decode()
assert '.steps-plan--featured' in css, 'Commercial stylesheet missing'
assert '.steps-brief-card' in css, 'Brief stylesheet missing'
print('RENDER_AND_ASSETS_OK|20 solutions|3 packages|7 FAQs|5 apps')
PY
sudo -n find /opt/dev_odoo18/odoo_agriculture/step_demo_homepage -type f ! -path '*/__pycache__/*' -exec sha256sum {} + | sort > "$stage/production-files.after"
cmp "$stage/production-files.before" "$stage/production-files.after"
curl -fsS https://stepsapp.cl/ -o "$stage/production.after.html"
python3 - "$stage" <<'PY'
from pathlib import Path
from lxml import html
import sys
p = Path(sys.argv[1])
before = html.fromstring((p / 'production.before.html').read_bytes())
after = html.fromstring((p / 'production.after.html').read_bytes())
assert [h.text_content() for h in before.xpath('//h1')] == [h.text_content() for h in after.xpath('//h1')]
assert not after.xpath('//*[@data-commercial-version="2026.10"]')
print('PRODUCTION_UNCHANGED')
PY
for route in / /contactus /web/login /soluciones/campo-y-produccion /soluciones/personas /soluciones/finanzas; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' "https://$host$route")
  test "$code" = 200
  echo "HTTP_OK|$host$route|$code"
done
sudo -n -u postgres psql -At -d "$db" -c "SELECT name,state,latest_version FROM ir_module_module WHERE name='step_demo_homepage'"
echo "DEPLOY_OK|$label|$backup|$log"
