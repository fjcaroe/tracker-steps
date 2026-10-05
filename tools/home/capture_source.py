"""Export public homepage templates only; no users, contacts or business data."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/tmp/steps-home-sys-source')
ROOT.mkdir(mode=0o755, exist_ok=True)
ROOT.chmod(0o755)  # Public templates only; allow the SSH user to download them.
sql = """SELECT json_agg(row_to_json(v)) FROM (
 SELECT id,key,website_id,active,name,arch_db,website_meta_title,
 website_meta_description,website_meta_keywords,website_meta_og_img
 FROM ir_ui_view WHERE active AND inherit_id IS NULL AND
 (key='website.homepage' OR key LIKE 'step_demo_homepage.%') ORDER BY key,website_id NULLS FIRST,id
) v;"""
raw = subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-d', 'karo_consultorias', '-Atc', sql], text=True)
views = json.loads(raw)
assert any(item['key'] == 'website.homepage' and item['website_id'] == 1 for item in views)
payload = {'source_database': 'karo_consultorias', 'source_website': 1, 'views': views}
destination = ROOT / 'public_templates.json'
destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print('PUBLIC_SOURCE_EXPORT_OK views=' + str(len(views)) + ' SHA256=' + hashlib.sha256(destination.read_bytes()).hexdigest())
for item in views:
    if item['key'] == 'website.homepage':
        print(json.dumps({'id': item['id'], 'website_id': item['website_id'], 'languages': list(item['arch_db']), 'sha256': hashlib.sha256(json.dumps(item['arch_db'], sort_keys=True).encode()).hexdigest()}))
subprocess.run(['tar', '-czf', str(ROOT / 'module.tar.gz'), '--exclude=__pycache__', '--exclude=*.pyc', '-C', '/opt/dev_odoo18/odoo_agriculture', 'step_demo_homepage'], check=True)
print('SOURCE_MODULE_SHA256=' + hashlib.sha256((ROOT / 'module.tar.gz').read_bytes()).hexdigest())
for host in ('stepsapp.cl', 'sys.stepsapp.cl'):
    result = subprocess.run(['curl', '--silent', '--show-error', '--max-time', '30', '--output', str(ROOT / (host + '.html')), '--write-out', '%{http_code}', 'https://' + host + '/'], text=True, capture_output=True)
    print(json.dumps({'host': host, 'status': result.stdout, 'exit_code': result.returncode, 'error': result.stderr[:200]}))
