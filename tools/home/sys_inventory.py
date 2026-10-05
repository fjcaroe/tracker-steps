"""Read-only routing and public-page metadata. Never print configuration secrets."""
import configparser
import json
from pathlib import Path
import subprocess

for path in ('/etc/odoo18.conf', '/etc/odoo18-sys.conf'):
    config = configparser.ConfigParser(interpolation=None)
    config.read(path)
    print(json.dumps({'config': path, **{key: config['options'].get(key) for key in ('db_name', 'dbfilter', 'addons_path', 'http_port')}}))
for path in Path('/etc/nginx/sites-enabled').glob('*'):
    content = path.read_text()
    if 'sys.stepsconsulting.cl' in content or 'sys.stepsapp.cl' in content:
        print('ROUTING_FILE=' + str(path))
        for line in content.splitlines():
            if line.strip().startswith(('listen ', 'server_name ', 'proxy_pass ', 'return ')):
                print(line.strip())
for db in ('karo_consultorias', 'SyS'):
    print('DATABASE=' + db)
    for sql in (
        "SELECT id,name,domain FROM website ORDER BY id;",
        "SELECT name,state,latest_version FROM ir_module_module WHERE name='step_demo_homepage';",
        "SELECT id,name,key,website_id,active,md5(arch_db::text) FROM ir_ui_view WHERE key='website.homepage' ORDER BY id;",
        "SELECT COUNT(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');",
    ):
        print(subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-d', db, '-Atc', sql], text=True).strip())
print(subprocess.check_output(['systemctl', 'show', 'odoo18-sys.service', '-p', 'User', '-p', 'WorkingDirectory', '-p', 'ExecStart'], text=True))
print(subprocess.check_output(['systemctl', 'list-units', '--all', '--plain', '--no-legend', '*odoo*', '*luis*'], text=True))
print(subprocess.check_output(['ss', '-ltnp', 'sport = :8070'], text=True))
pid = subprocess.check_output(['systemctl', 'show', 'odoo18-sys.service', '-p', 'MainPID', '--value'], text=True).strip()
if pid != '0':
    proc = Path('/proc') / pid
    argv = (proc / 'cmdline').read_bytes().decode().split('\0')
    safe = [argv[0]]
    for i, arg in enumerate(argv[:-1]):
        if arg in ('-c', '--config', '-d', '--database', '--http-port'):
            safe.extend([arg, argv[i + 1]])
    print(json.dumps({'main_pid': pid, 'exe': str((proc / 'exe').resolve()), 'cwd': str((proc / 'cwd').resolve()), 'safe_arguments': safe}))
for directory in ('/opt/odoo18-sys', '/opt/luis_odoo18/odoo_agriculture', '/opt/dev_odoo18/odoo_agriculture'):
    print(json.dumps({'directory': directory, 'exists': Path(directory).is_dir()}))
