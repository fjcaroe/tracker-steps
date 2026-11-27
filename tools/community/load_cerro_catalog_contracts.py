"""Run the official upgrade retaining originally mandatory fields of omitted Cerro applications."""
import hashlib
import inspect
import json
from pathlib import Path
import sys

RUNTIME = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
PLANS = {
    'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M': Path('/opt/steps-validation/community-cerro-contracts-20261127U44M/original-required.json'),
    'COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P': Path('/opt/steps-validation/community-cerro-concepts-20261127U45P/original-required.json'),
}
LOCAL_PLANS = {
    'COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P': 'concepts',
    'COMMUNITY_CERRO_BOM_PACKING_20261127U46A': 'packing',
    'COMMUNITY_CERRO_BOM_PACKING_20261127U46B': 'packing-b',
}
SQL_SHA = '0470f3e4cfa2736ca1b402bad8e5047edb39fc79d68de2ae6f81853318722bff'
LOOKUP = """SELECT f.id,f.model,format_type(a.atttypid,a.atttypmod),d.module
    FROM pg_attribute a JOIN ir_model_fields f ON f.name=a.attname AND f.model=%s
    JOIN ir_model_data d ON d.res_id=f.id AND d.model='ir.model.fields' AND d.id=%s
    WHERE a.attrelid=to_regclass(%s) AND a.attname=%s AND a.attnotnull AND NOT a.attisdropped"""


def main():
    args=sys.argv[1:]
    database=args[args.index('-d')+1] if args.count('-d')==1 else None
    if database not in (LOCAL_PLANS if '--cerro-local-qa' in args else PLANS) or '--db-filter=^'+database+'$' not in args:
        raise ValueError('Unexpected database for the Cerro trial loader')
    from stat import S_IMODE
    runtime=RUNTIME
    path=PLANS.get(database)
    if '--cerro-local-qa' in args:
        args.remove('--cerro-local-qa')
        cold = '--db_host=/dev/shm/steps-cerro-u46/socket' in args and '--db_port=55443' in args
        assert (cold and LOCAL_PLANS[database] in ('packing','packing-b')) or ('--db_host=/work/cerro-pg/socket' in args and '--db_port=55442' in args)
        runtime=Path('/work/sys-fg-code')
        path=Path('/dev/shm/steps-cerro-u46' if cold else '/work/cerro-pg')/LOCAL_PLANS[database]/'original-required.json'
    if path.stat().st_uid!=0 or S_IMODE(path.stat().st_mode) & 0o022:
        raise ValueError('The original field inventory must belong to the validation operator')
    plan=json.loads(path.read_bytes())
    assert plan['database']==database and len(plan['fields'])==29
    sys.path.insert(0,str(runtime))
    from odoo import cli
    from odoo.tools import sql
    source=runtime/'odoo/tools/sql.py'
    assert Path(inspect.getsourcefile(sql.drop_not_null)).resolve()==source.resolve()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==SQL_SHA
    original=sql.drop_not_null
    checked=set()

    def drop_not_null(cr, table, column):
        key=table+'.'+column
        if cr.dbname!=database or key not in plan['fields']:
            return original(cr,table,column)
        field_id,model,sql_type,owner,alias_id=plan['fields'][key]
        cr.execute(LOOKUP,(model,alias_id,'public.'+table,column))
        assert cr.fetchall()==[(field_id,model,sql_type,owner)]
        checked.add(key)

    sql.drop_not_null=drop_not_null
    try:
        sys.argv=[str(runtime/'odoo-bin'),*args]
        cli.main()
    finally:
        sql.drop_not_null=original
        print('CERRO_RETAINED_REQUIRED',json.dumps(sorted(checked)),flush=True)


if __name__=='__main__':
    main()
