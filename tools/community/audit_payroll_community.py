"""Cerro-only read-only source/API audit. No employee data, secrets or rule bodies exported.

Run on the documented SSH host as root. Output belongs outside the checkout.
This is a compatibility inventory, not payroll/normative certification.
"""
import argparse
import ast
import configparser
import hashlib
import json
from pathlib import Path
import subprocess

MODULES = ('l10n_cl_simpledigital_payroll', 'hr_payroll', 'hr_payroll_account',
           'hr_payroll_expense', 'hr_work_entry_contract_enterprise',
           'step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_remuneration_book',
           'step_hr_contract_lifecycle', 'step_hr_contract_lifecycle_agriculture',
           'steps_hr_payroll_correction', 'step_payroll_engine_transition', 'l10n_cl_hr',
           'step_hr_contract_lifecycle_simpledigital','step_hr_payroll_rounding','step_hr_contract_days')


def query(sql):
    result = subprocess.run(['sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
        'psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-d', 'CERRO_EL_PLOMO', '-c', sql],
        check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line not in ('BEGIN', 'COMMIT')]


def source(directory):
    manifest = ast.literal_eval((directory / '__manifest__.py').read_text(encoding='utf-8-sig'))
    classes = []
    for path in sorted(directory.rglob('*.py')):
        if 'tests' in path.parts or 'tools' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            attrs = {node.targets[0].id: node.value for node in cls.body
                     if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
            models = {}
            for key in ('_name', '_inherit'):
                if key in attrs:
                    models[key] = ast.literal_eval(attrs[key])
            methods = {node.name: ast.unparse(node.args) for node in cls.body
                       if isinstance(node, ast.FunctionDef)}
            fields = sorted(key for key, node in attrs.items() if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'fields')
            super_calls = sorted({node.func.attr for node in ast.walk(cls)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name)
                and node.func.value.func.id == 'super'})
            refs = sorted({node.value for node in ast.walk(cls) if isinstance(node, ast.Constant)
                and isinstance(node.value, str) and node.value.startswith(('hr.', 'l10n.'))
                and ' ' not in node.value})
            if models or refs:
                classes.append({'file':str(path.relative_to(directory)), 'models':models,
                    'fields':fields, 'methods':methods, 'super_calls':super_calls, 'model_refs':refs})
    hashes = {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(directory.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
              and '.git' not in p.parts}
    return {'manifest':{key:manifest.get(key) for key in ('version','license','depends')},
            'classes':classes, 'files':len(hashes),
            'source_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oca',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert str(args.output.resolve()).startswith('/opt/steps-validation/'), 'Private artifact output required'
    config=configparser.ConfigParser(interpolation=None)
    assert config.read('/etc/odoo18-cerroelplomo.conf')
    assert config['options']['db_name']=='CERRO_EL_PLOMO'
    roots=[Path(p.strip()) for p in config['options']['addons_path'].split(',')]
    assert query('SHOW default_transaction_read_only')==['on']
    result={'database':'CERRO_EL_PLOMO','read_only':True,'read_only_session':'on','modules':{}}
    for name in MODULES:
        directory=next((root/name for root in roots if (root/name/'__manifest__.py').exists()),None)
        result['modules'][name]=source(directory) if directory else None
    assert subprocess.run(['git','-C',str(args.oca),'remote','get-url','origin'],check=True,
        capture_output=True,text=True).stdout.strip()=='https://github.com/OCA/payroll.git'
    assert not subprocess.run(['git','-C',str(args.oca),'status','--porcelain'],check=True,
        capture_output=True,text=True).stdout.strip()
    result['oca']={'revision':subprocess.run(['git','-C',str(args.oca),'rev-parse','HEAD'],check=True,
        capture_output=True,text=True).stdout.strip(),'payroll':source(args.oca/'payroll'),
        'payroll_account':source(args.oca/'payroll_account')}
    result['schema']=json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('model',model,'name',name,'ttype',ttype,'relation',relation,'store',store,'required',required) ORDER BY model,name),'[]'::jsonb) FROM ir_model_fields WHERE model LIKE 'hr.pay%' OR model LIKE 'hr.salary.%' OR model LIKE 'hr.contract%' OR model LIKE 'hr.work.entry%' OR model LIKE 'step.previred.%' OR model LIKE 'step.remuneration.%'")[0])
    counts={}
    for table in ('hr_contract','hr_payslip','hr_payslip_run','hr_payslip_input','hr_payslip_line',
                  'hr_payroll_structure','hr_payroll_structure_type','hr_salary_rule','hr_payslip_input_type',
                  'step_payroll_legacy_snapshot','hr_salary_employee_month','hr_work_entry','hr_employee_movement','hr_employee_movement_line','hr_employee_movement_type',
                  'step_previred_profile','step_previred_batch','step_remuneration_book_profile','step_remuneration_book_profile_line',
                  'step_remuneration_book_log'):
        exists=query("SELECT to_regclass('"+table+"') IS NOT NULL")[0]=='t'
        counts[table]=int(query('SELECT count(*) FROM '+table)[0]) if exists else None
    result['counts']=counts
    result['states']=json.loads(query("SELECT coalesce(json_object_agg(state,n),'{}'::json) FROM (SELECT state,count(*) n FROM hr_payslip GROUP BY state) t")[0])
    result['rule_xmlid_namespaces']=json.loads(query("SELECT coalesce(json_object_agg(module,n),'{}'::json) FROM (SELECT d.module,count(DISTINCT r.id) n FROM hr_salary_rule r JOIN ir_model_data d ON d.model='hr.salary.rule' AND d.res_id=r.id GROUP BY d.module) t")[0])
    rules=json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'code',code,'struct_id',struct_id,'category_id',category_id,'sequence',sequence,'active',active,'condition',condition_python,'amount',amount_python_compute) ORDER BY id),'[]'::jsonb) FROM hr_salary_rule")[0])
    result['structures']=json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'type_id',type_id,'code',code,'active',active) ORDER BY id),'[]'::jsonb) FROM hr_payroll_structure")[0])
    result['input_types']=json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'code',code,'active',active) ORDER BY id),'[]'::jsonb) FROM hr_payslip_input_type")[0])
    result['rules']=[]
    for rule in rules:
        item={key:rule[key] for key in ('id','code','struct_id','category_id','sequence','active')}
        for key in ('condition','amount'):
            code=rule[key] or ''
            item[key+'_sha256']=hashlib.sha256(code.encode()).hexdigest()
            try:
                tree=ast.parse(code)
                item[key+'_attributes']=sorted({ast.unparse(n) for n in ast.walk(tree) if isinstance(n,ast.Attribute)})
            except SyntaxError:
                item[key+'_parse_error']=True
        result['rules'].append(item)
    result['installed']=json.loads(query("SELECT jsonb_build_object('all',count(*),'enterprise',count(*) FILTER (WHERE license='OEEL-1'),'own',count(*) FILTER (WHERE name LIKE 'step_%')) FROM ir_module_module WHERE state='installed'")[0])
    modules=json.loads(query("SELECT jsonb_agg(jsonb_build_object('name',m.name,'license',m.license,'depends',(SELECT coalesce(jsonb_agg(d.name ORDER BY d.name),'[]'::jsonb) FROM ir_module_module_dependency d WHERE d.module_id=m.id)) ORDER BY m.name) FROM ir_module_module m WHERE m.state='installed'")[0])
    for module in modules:
        directory=next((root/module['name'] for root in roots if (root/module['name']/'__manifest__.py').exists()),None)
        if directory:
            manifest=ast.literal_eval((directory/'__manifest__.py').read_text(encoding='utf-8-sig'))
            module['manifest_depends']=manifest.get('depends',[])
    result['dependency_inventory']={'modules':modules}
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'read_only':True,'output':str(args.output),'counts':counts,'installed':result['installed'],
                      'oca_revision':result['oca']['revision']}))


if __name__=='__main__':
    main()
