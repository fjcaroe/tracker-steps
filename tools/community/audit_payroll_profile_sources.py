"""Read-only origin metadata for Chile configuration; no formulas or employee data."""
import argparse
import ast
import configparser
import hashlib
import json
from pathlib import Path
import subprocess

PROFILES={'cerro':'/etc/odoo18-cerroelplomo.conf','sys':'/etc/odoo18-sys.conf'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert str(a.output.resolve()).startswith('/opt/steps-validation/')
    result={'read_only':True,'formula_bodies_exported':False,'employee_data_exported':False,'financial_certified':False,'profiles':{}}
    for key,path in PROFILES.items():
        cfg=configparser.ConfigParser(interpolation=None);assert cfg.read(path)
        db=cfg['options']['db_name']
        def query(text):
            return subprocess.run(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
                'psql','-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',text],check=True,text=True,capture_output=True).stdout.strip()
        assert query('SHOW default_transaction_read_only')=='on'
        kind=query("SELECT udt_name FROM information_schema.columns WHERE table_name='hr_payroll_structure' AND column_name='name'")
        name="s.name->>'en_US'" if kind=='jsonb' else 's.name'
        raw=query("SELECT coalesce(jsonb_agg(jsonb_build_object('id',r.id,'code',r.code,'active',r.active,'sequence',r.sequence,'structure_id',s.id,'category_id',r.category_id,'body',r.amount_python_compute) ORDER BY r.id),'[]'::jsonb) FROM hr_salary_rule r JOIN hr_payroll_structure s ON s.id=r.struct_id WHERE "+name+"='Nómina Chile' AND r.code IN ('BASIC','GROSS','NET')")
        rules=json.loads(raw)
        for row in rules:
            body=row.pop('body') or '';row['body_sha256']=hashlib.sha256(body.encode()).hexdigest()
            refs=set()
            try:
                for node in ast.walk(ast.parse(body)):
                    if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id=='categories' and isinstance(node.slice,ast.Constant):refs.add(node.slice.value)
                    if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='categories':refs.add(node.attr)
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='categories' and node.func.attr=='get' and node.args and isinstance(node.args[0],ast.Constant):refs.add(node.args[0].value)
                row['category_references']=sorted(str(x) for x in refs)
            except SyntaxError:row['parse_error']=True
        categories=json.loads(query("SELECT jsonb_agg(jsonb_build_object('id',id,'code',code,'parent_id',parent_id) ORDER BY id) FROM hr_salary_rule_category WHERE code IN ('BASIC','IMP','ALW','GROSS','NET')"))
        result['profiles'][key]={'rules':rules,'categories':categories,'active_essential_ids':{code:[r['id'] for r in rules if r['active'] and r['code']==code] for code in ('BASIC','GROSS','NET')}}
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value['active_essential_ids'] for key,value in result['profiles'].items()}))


if __name__=='__main__':main()
