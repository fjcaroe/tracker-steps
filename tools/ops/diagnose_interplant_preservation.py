"""Read-only preservation diagnostics for a failed private T209 validation."""
import json
from pathlib import Path
import manage_management as management
root=Path('/opt/steps-validation/management_development_t209d')
db='MANAGEMENT_QA_DEVELOPMENT_t209d'
before=json.loads((root/'business_before.json').read_text())
management.TICKET_REVISION='reception-excel'
management.SETTINGS=True
management.BUSINESS=tuple(before)
management.PROMOTION_COLUMNS=json.loads(management.query(db,"SELECT json_object_agg(table_name,cols) FROM (SELECT table_name,json_agg(column_name) cols FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) s"))
after=management.snapshot(db)
print('PRESERVATION_CHANGED_TABLES', [key for key in before if before[key]!=after.get(key)])
print('PACKAGE_BEFORE',before['stock_quant_package'])
print('PACKAGE_AFTER',after['stock_quant_package'])

import subprocess
sql_dump=subprocess.check_output(['pg_restore','-f','-','--data-only','--table=stock_quant_package',str(root/'source.dump')],text=True)
lines=sql_dump.splitlines()
start=next(i for i,line in enumerate(lines) if line.startswith('COPY public.stock_quant_package ('))
columns=lines[start].split('(',1)[1].split(')',1)[0].split(', ')
old=[]
for line in lines[start+1:]:
    if line == r'\.': break
    values=dict(zip(columns,line.split('\t')))
    old.append((int(values['id']),None if values['step_packing_company_id']==r'\N' else int(values['step_packing_company_id'])))
values=','.join('(%d,%s)'%(key,'NULL' if company is None else company) for key,company in old)
old_cte='WITH old(id,company) AS (VALUES '+values+') '
assert management.query(db,old_cte+"SELECT count(*) FROM stock_quant_package t JOIN old ON t.id=old.id WHERE t.step_packing_company_id IS DISTINCT FROM old.company AND NOT (old.company IS NULL AND t.is_fruit_tag AND t.company_id=t.step_packing_company_id)")=='0'
row="(to_jsonb(t) || jsonb_build_object('step_packing_company_id',old.company))"
original_hash=management.query(db,old_cte+"SELECT json_build_object('count',count(*),'digest',md5(COALESCE(string_agg("+row+"::text,'|' ORDER BY "+row+"::text),'')))::text FROM stock_quant_package t JOIN old ON t.id=old.id")
assert json.loads(original_hash)==json.loads(before['stock_quant_package'])
assert [key for key in before if before[key]!=after.get(key)]==['stock_quant_package']
print('ONLY_EXPECTED_NATIVE_COMPANY_BACKFILL_CONFIRMED')
