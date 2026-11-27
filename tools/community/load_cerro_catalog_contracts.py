"""Run the official upgrade retaining originally mandatory fields of omitted Cerro applications."""
import hashlib
import inspect
import json
from pathlib import Path
import sys

RUNTIME = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
DB = 'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M'
PLAN = Path('/opt/steps-validation/community-cerro-contracts-20261127U44M/original-required.json')
SQL_SHA = '0470f3e4cfa2736ca1b402bad8e5047edb39fc79d68de2ae6f81853318722bff'
LOOKUP = """SELECT f.id,f.model,format_type(a.atttypid,a.atttypmod),d.module
    FROM pg_attribute a JOIN ir_model_fields f ON f.name=a.attname AND f.model=%s
    JOIN ir_model_data d ON d.res_id=f.id AND d.model='ir.model.fields' AND d.id=%s
    WHERE a.attrelid=to_regclass(%s) AND a.attname=%s AND a.attnotnull AND NOT a.attisdropped"""


def main():
    args=sys.argv[1:]
    if args.count('-d')!=1 or args[args.index('-d')+1]!=DB or '--db-filter=^'+DB+'$' not in args:
        raise ValueError('Unexpected database for the Cerro trial loader')
    from stat import S_IMODE
    if PLAN.stat().st_uid!=0 or S_IMODE(PLAN.stat().st_mode) & 0o022:
        raise ValueError('The original field inventory must belong to the validation operator')
    plan=json.loads(PLAN.read_bytes())
    assert plan['database']==DB and len(plan['fields'])==29
    sys.path.insert(0,str(RUNTIME))
    from odoo import cli
    from odoo.tools import sql
    source=RUNTIME/'odoo/tools/sql.py'
    assert Path(inspect.getsourcefile(sql.drop_not_null)).resolve()==source.resolve()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==SQL_SHA
    original=sql.drop_not_null
    checked=set()

    def drop_not_null(cr, table, column):
        key=table+'.'+column
        if cr.dbname!=DB or key not in plan['fields']:
            return original(cr,table,column)
        field_id,model,sql_type,owner,alias_id=plan['fields'][key]
        cr.execute(LOOKUP,(model,alias_id,'public.'+table,column))
        assert cr.fetchall()==[(field_id,model,sql_type,owner)]
        checked.add(key)

    sql.drop_not_null=drop_not_null
    try:
        sys.argv=[str(RUNTIME/'odoo-bin'),*args]
        cli.main()
    finally:
        sql.drop_not_null=original
        print('CERRO_RETAINED_REQUIRED',json.dumps(sorted(checked)),flush=True)


if __name__=='__main__':
    main()
