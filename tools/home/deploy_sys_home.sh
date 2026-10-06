#!/usr/bin/env bash
# SyS production only. The release is a git archive of an already pushed commit.
set -euo pipefail
archive=${1:?Usage: deploy_sys_home.sh ARCHIVE SHA256 COMMIT}
expected=${2:?SHA256 required}
commit=${3:?Published git commit required}
[[ "$expected" =~ ^[a-f0-9]{64}$ && "$commit" =~ ^[a-f0-9]{40}$ ]]
db=SyS
service=odoo18-sys.service
config=/etc/odoo18-sys.conf
addons=/opt/luis_odoo18/odoo_agriculture
python=/opt/odoo18/venv/bin/python
echo "$expected  $archive" | sha256sum -c -
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/steps_backups/home-sys-production-$stamp
stage=$(mktemp -d /tmp/steps-home-sys.XXXXXX)
chmod 0755 "$stage"
stopped=0
trap 'if [ "$stopped" = 1 ]; then sudo -n systemctl start "$service"; fi' EXIT
tar -xzf "$archive" -C "$stage"
sudo -n systemctl is-active --quiet "$service"
sudo -n -u odoo "$python" - "$config" "$addons" "$stage" <<'PY'
import ast, sys
from pathlib import Path
sys.path.insert(0, '/opt/odoo18')
import odoo
from lxml import etree
odoo.tools.config.parse_config(['-c', sys.argv[1], '-d', 'SyS'])
odoo.modules.module.initialize_sys_path()
assert Path(odoo.modules.module.get_module_path('step_demo_homepage')).resolve() == \
    Path(sys.argv[2] + '/step_demo_homepage').resolve(), 'Unexpected module path'
module = Path(sys.argv[3]) / 'step_demo_homepage'
assert ast.literal_eval((module / '__manifest__.py').read_text())['version'] == '18.0.2.5.1'
tree = etree.parse(str(module / 'views/homepage.xml'))
assert len(tree.xpath('//article[@class="steps-product"]')) == 20
assert tree.xpath('//*[@data-commercial-version="2026.10"]')
print('PREFLIGHT_MODULE_OK')
PY
test "$(sudo -n -u postgres psql -At -d "$db" -c "SELECT count(*) FROM website")" = 1
test "$(sudo -n -u postgres psql -At -d "$db" -c "SELECT state FROM ir_module_module WHERE name='step_demo_homepage'")" = installed
test "$(sudo -n -u postgres psql -At -d "$db" -c "SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")" = 0
sudo -n install -d -m 0750 "$backup"
sudo -n cp -a "$config" "$backup/odoo.conf.before"
sudo -n tar -czf "$backup/module.before.tar.gz" -C "$addons" step_demo_homepage
# Record the source content and module files before touching the separate SyS service.
sudo -n -u postgres psql -At -d karo_consultorias -c "SELECT id,key,website_id,md5(arch_db::text) FROM ir_ui_view WHERE key='website.homepage' OR key LIKE 'step_demo_homepage.%' ORDER BY id" > "$stage/source-views.before"
sudo -n find /opt/dev_odoo18/odoo_agriculture/step_demo_homepage -type f ! -path '*/__pycache__/*' -exec sha256sum {} + | sort > "$stage/source-files.before"
curl -fsS https://stepsapp.cl/ -o "$stage/source.before.html"
curl -fsS https://sys.stepsapp.cl/ -o "$stage/sys.before.html"
sudo -n systemctl stop "$service"
stopped=1
sudo -n -u postgres pg_dump -Fc --lock-wait-timeout=15000 -d "$db" -f "/tmp/home-sys-$stamp.dump"
sudo -n mv "/tmp/home-sys-$stamp.dump" "$backup/database.before.dump"
sudo -n rsync -a "$stage/step_demo_homepage/" "$addons/step_demo_homepage/"
sudo -n chown -R odoo:odoo "$addons/step_demo_homepage"
log=/tmp/home-sys-upgrade-$stamp.log
if ! sudo -n -u odoo "$python" /opt/odoo18/odoo-bin -c "$config" -d "$db" \
    -u step_demo_homepage --stop-after-init --no-http --workers=0 --max-cron-threads=0 \
    --without-demo=all --logfile="$log" > "$stage/upgrade.stdout" 2>&1; then
    sudo -n tar -xzf "$backup/module.before.tar.gz" -C "$addons"
    sudo -n cp "$log" "$backup/upgrade.failed.log"
    echo "UPGRADE_FAILED; previous code restored; backup=$backup" >&2
    tail -60 "$log"
    exit 1
fi
sudo -n cp "$log" "$backup/upgrade.log"
printf 'commit=%s\narchive_sha256=%s\n' "$commit" "$expected" > "$stage/release.txt"
sudo -n cp "$stage/release.txt" "$backup/release.txt"
sudo -n systemctl start "$service"
stopped=0
curl -fsS --retry 30 --retry-connrefused --retry-delay 2 https://sys.stepsapp.cl/ -o "$stage/sys.after.html"
sudo -n -u odoo "$python" "$stage/tools/home/verify_public_home.py"
sudo -n -u postgres psql -At -d karo_consultorias -c "SELECT id,key,website_id,md5(arch_db::text) FROM ir_ui_view WHERE key='website.homepage' OR key LIKE 'step_demo_homepage.%' ORDER BY id" > "$stage/source-views.after"
sudo -n find /opt/dev_odoo18/odoo_agriculture/step_demo_homepage -type f ! -path '*/__pycache__/*' -exec sha256sum {} + | sort > "$stage/source-files.after"
cmp "$stage/source-views.before" "$stage/source-views.after"
cmp "$stage/source-files.before" "$stage/source-files.after"
sudo -n cp "$stage"/*.html "$backup/"
sudo -n systemctl is-active --quiet "$service"
sudo -n -u postgres psql -At -d "$db" -c "SELECT name,state,latest_version FROM ir_module_module WHERE name='step_demo_homepage'"
echo "DEPLOY_OK|https://sys.stepsapp.cl/|SOURCE_UNCHANGED|$backup|$commit"
