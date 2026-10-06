"""Read payroll engine dependencies, history counts and source manifests safely."""
import ast
import configparser
import json
from pathlib import Path
import subprocess


def query(database, sql):
    value = subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-d', database, '-Atc', sql], text=True).strip()
    return json.loads(value or 'null')


registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
for name, target in registry['environments'].items():
    if name not in ('development', 'demo-sys', 'sys', 'steps', 'cerro'):
        continue
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    paths = [Path(p.strip()) for p in cfg['options']['addons_path'].split(',')]
    database = target['database']
    modules = query(database, "SELECT json_agg(t) FROM (SELECT name,state,latest_version FROM ir_module_module WHERE name LIKE '%payroll%' OR name LIKE 'l10n_cl_hr%' OR name LIKE 'step_hr%' OR name LIKE 'steps_hr%' ORDER BY name) t")
    for module in modules:
        source = next((p / module['name'] / '__manifest__.py' for p in paths if (p / module['name'] / '__manifest__.py').exists()), None)
        if source:
            metadata = ast.literal_eval(source.read_text())
            module.update(source=str(source.parent), manifest_version=metadata.get('version'), depends=metadata.get('depends', []))
    counts = {}
    for table in ('hr_payslip', 'hr_salary_rule', 'hr_payroll_structure'):
        exists = query(database, "SELECT to_json(to_regclass('%s')::text)" % table)
        if exists:
            counts[table] = query(database, "SELECT to_json(count(*)) FROM " + table)
    dependencies = query(database, "SELECT json_agg(t) FROM (SELECT m.name,d.name AS dependency FROM ir_module_module_dependency d JOIN ir_module_module m ON m.id=d.module_id WHERE m.state='installed' AND d.name IN ('l10n_cl_hr','l10n_cl_simpledigital_payroll') ORDER BY m.name) t")
    roots = query(database, "SELECT json_agg(t) FROM (SELECT m.id,m.name,m.active,d.module,d.name AS xmlid FROM ir_ui_menu m LEFT JOIN ir_model_data d ON d.model='ir.ui.menu' AND d.res_id=m.id WHERE m.parent_id IS NULL ORDER BY m.id) t")
    print(json.dumps({'environment': name, 'modules': modules, 'counts': counts, 'dependents': dependencies, 'root_menus': roots}, ensure_ascii=False))
