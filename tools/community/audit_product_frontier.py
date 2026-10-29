"""Read-only installed-module/source inventory for all three production products.

No ORM, business data, credentials or source bodies are exported. Private output
contains deployment paths and module metadata; publish only reviewed aggregates.
"""
import argparse
import ast
import configparser
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert str(args.output.resolve()).startswith('/opt/steps-validation/')
    registry=json.loads(args.registry.read_text(encoding='utf-8-sig'))
    profiles={name:row for name,row in registry['environments'].items() if row['role']=='production'}
    assert set(profiles)=={'cerro','steps','sys'}
    result={'read_only':True,'orm_loaded':False,'business_data_exported':False,
            'source_bodies_exported':False,'enterprise_sources_copied':False,
            'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'products':{}}
    for name,row in profiles.items():
        config=configparser.ConfigParser(interpolation=None);assert config.read(row['config'])
        database=config['options']['db_name'];assert database==row['database']
        def query(statement):
            return subprocess.check_output(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
                'psql','-XAt','-v','ON_ERROR_STOP=1','-d',database,'-c',statement],text=True).strip()
        assert query('SHOW default_transaction_read_only')=='on'
        modules=json.loads(query("SELECT jsonb_agg(jsonb_build_object('name',m.name,'version',m.latest_version,'license',m.license,"
            "'depends',(SELECT coalesce(jsonb_agg(d.name ORDER BY d.name),'[]'::jsonb) FROM ir_module_module_dependency d WHERE d.module_id=m.id)) ORDER BY m.name) "
            "FROM ir_module_module m WHERE m.state='installed'"))
        roots=[Path(value.strip()) for value in config['options']['addons_path'].split(',')]
        for module in modules:
            source=next((root/module['name'] for root in roots if (root/module['name']/'__manifest__.py').exists()),None)
            module['source_available']=source is not None
            if source:
                manifest=ast.literal_eval((source/'__manifest__.py').read_text(encoding='utf-8-sig'))
                module['manifest']={key:manifest.get(key) for key in ('version','license','depends')}
                if module['name'].startswith('step') or module['name']=='l10n_cl_simpledigital_payroll':
                    assert manifest.get('license')!='OEEL-1','Do not inventory Enterprise bodies as owned source'
                    files={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob('*'))
                           if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.xml','.csv','.js','.scss','.css','.html')}
                    module['owned_source']={'path':str(source),'files':len(files),
                        'fingerprint_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()}
        own=[module for module in modules if module['name'].startswith('step')]
        result['products'][name]={'modules':modules,'installed':len(modules),
            'enterprise':sum(module['license']=='OEEL-1' for module in modules),
            'own':len(own),'own_without_source':[module['name'] for module in own if not module['source_available']]}
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({name:{key:value for key,value in row.items() if key!='modules'} for name,row in result['products'].items()}))


if __name__=='__main__':main()
