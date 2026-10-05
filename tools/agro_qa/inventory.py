"""Read-only environment metadata for integrated agricultural QA, no secrets."""
import configparser
import json
from pathlib import Path
import subprocess


def query(database, sql):
    return subprocess.check_output(['sudo', '-n', '-u', 'postgres', 'psql', '-d', database,
                                    '-Atc', sql], text=True).strip()


print(query('postgres', "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"))
for path in sorted(Path('/etc').glob('*odoo*.conf')):
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(path)
    except configparser.Error:
        print(json.dumps({'config': str(path), 'parseable': False}))
        continue
    if 'options' not in config:
        continue
    opts = config['options']
    print(json.dumps({'config': str(path), **{key: opts.get(key) for key in (
        'db_name', 'dbfilter', 'http_port', 'addons_path', 'data_dir', 'db_user')}}))
for database in ('LAB_TAREAS', 'STEPS_DEMO', 'steps_qa', 'STEPS_DEMO_SYS'):
    try:
        print(json.dumps({'database': database, 'modules': query(database,
            "SELECT name,state,latest_version FROM ir_module_module WHERE name IN "
            "('step_packing','step_inventory_fruit_tag','step_inventory_packing',"
            "'step_packing_operations','step_producers','step_producer_fruit_flow','step_export',"
            "'step_dispatch_guide','step_hr','step_management_costs','step_management_costs_agriculture') "
            "ORDER BY name")}))
    except subprocess.CalledProcessError:
        print(json.dumps({'database': database, 'available': False}))
print(subprocess.check_output(['systemctl', 'list-units', '--all', '--type=service',
                              '--no-pager', 'odoo*'], text=True))
