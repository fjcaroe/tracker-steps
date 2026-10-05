#!/usr/bin/env bash
set -euo pipefail
ARCHIVE=${1:?Code archive required}
EXPECTED_SHA=${2:?SHA256 required}
ROOT=/opt/steps-assistant-validation
DB=STEPS_ASSISTANT_TEST_20261005
RUN_LOG="$ROOT/tests-$(date -u +%Y%m%dT%H%M%SZ).log"
test "$(sha256sum "$ARCHIVE" | cut -d ' ' -f 1)" = "$EXPECTED_SHA"
sudo install -d -m 0755 -o odoo -g odoo "$ROOT" "$ROOT/addons" "$ROOT/data"
sudo tar -xzf "$ARCHIVE" -C "$ROOT/addons" --no-same-owner
sudo chown -R odoo:odoo "$ROOT/addons/step_support_assistant"
if test -d "$ROOT/addons/step_support_assistant_knowledge"; then
    sudo chown -R odoo:odoo "$ROOT/addons/step_support_assistant_knowledge"
fi
DB_ROLE=$(sudo -u odoo /usr/bin/python3.10 -c "import configparser; c=configparser.ConfigParser(); c.read('/etc/dev_odoo18.conf'); print(c.get('options','db_user',fallback='odoo'))")
ADDONS=$(sudo -u odoo /usr/bin/python3.10 -c "import configparser; c=configparser.ConfigParser(); c.read('/etc/dev_odoo18.conf'); print(c.get('options','addons_path'))")
if ! sudo -u postgres psql -Atc "SELECT 1 FROM pg_database WHERE datname='$DB';" | grep -q '^1$'; then
    sudo -u postgres createdb -O "$DB_ROLE" "$DB"
fi
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf \
    -d "$DB" -i step_support_assistant,step_support_assistant_knowledge -u step_support_assistant,step_support_assistant_knowledge \
    --addons-path="$ROOT/addons,$ADDONS" --data-dir="$ROOT/data" \
    --workers=0 --max-cron-threads=0 --no-http --stop-after-init \
    --http-interface=127.0.0.1 --http-port=0 \
    --without-demo=all --test-enable --test-tags /step_support_assistant,/step_support_assistant_knowledge \
    --logfile="$RUN_LOG"
sudo grep -E 'Starting AssistantTests|Starting KnowledgeSourceTests|0 failed|ERROR|FAIL|modules loaded' "$RUN_LOG" | tail -n 50
printf 'ASSISTANT_TEST_RUN_OK\nLOG=%s\n' "$RUN_LOG"
