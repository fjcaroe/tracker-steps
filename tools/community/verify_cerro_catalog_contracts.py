"""Verify the corrected Cerro catalogue across official upgrade, restart, original security and SQL."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg2

from audit_cerro_original_schema import capture
from check_cerro_catalog_contracts import DB, DEST, MODULE, PACKET, frozen_report
from check_cerro_combined_budget import guard, BUDGET, PACKAGE
from check_cerro_export_contacts import CONTACTS, directory
from check_cerro_freight_directory import FREIGHT
from check_cerro_schema_counterexamples import NATIVE_SOURCE, native_read, verify
from compare_cerro_studio_receipts import receipt
from check_cerro_studio_strict import ROOT, addon_roots, run
from restore_cerro_bom_before_guard import FINAL_TARGET, all_guards
from restore_cerro_studio_strict import module_census


def make_plan(keys):
    with psycopg2.connect(dbname=NATIVE_SOURCE) as conn, conn.cursor() as cr:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        inventory={}
        for schema,table,field in keys:
            model=table.replace('_','.')
            cr.execute("""SELECT f.id,f.model,format_type(a.atttypid,a.atttypmod),d.module,d.id
                FROM pg_attribute a JOIN ir_model_fields f ON f.model=%s AND f.name=a.attname
                JOIN ir_model_data d ON d.model='ir.model.fields' AND d.res_id=f.id
                WHERE a.attrelid=to_regclass(%s) AND a.attname=%s AND a.attnotnull
                AND f.required AND f.store AND NOT a.attisdropped""",(model,schema+'.'+table,field))
            row,=cr.fetchall()
            inventory[table+'.'+field]=row
        assert len(inventory)==29
        return dict(database=DB,fields=inventory)


def checked_catalogue():
    result=capture({'native':NATIVE_SOURCE,'before':FINAL_TARGET,'corrected':DB},
                   [('native','corrected'),('before','corrected')])
    raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    return raw


def original_rows(database):
    tables=['step_fruit_category_company_rel','step_fruit_class_company_rel','step_caliber_group_company_rel',
            'step_fruit_caliber_company_rel','step_management_fruit_category','step_management_fruit_class',
            'step_management_caliber_group','step_management_fruit_caliber','stock_package_type']
    from psycopg2 import sql
    with psycopg2.connect(dbname=database) as conn, conn.cursor() as cr:
        conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
        result={}
        for table in tables:
            cr.execute(sql.SQL("SELECT count(*),md5(string_agg(to_jsonb(t)::text,chr(10) ORDER BY to_jsonb(t)::text)) FROM {} t").format(sql.Identifier(table)))
            result[table]=cr.fetchone()
        return result


def subprocess_output(phase,input_data=None):
    return subprocess.check_output(['runuser','-u','postgres','--','/usr/bin/python3.10',str(Path(__file__).resolve()),phase], input=input_data)


def main():
    if len(sys.argv)==2:
        if sys.argv[1]=='plan':
            keys=json.load(sys.stdin)
            print(json.dumps(make_plan(keys),sort_keys=True))
        elif sys.argv[1]=='result':
            sys.stdout.buffer.write(checked_catalogue())
        elif sys.argv[1]=='rows':
            native,current=original_rows(NATIVE_SOURCE),original_rows(DB)
            assert native==current, {key for key in native if native[key]!=current[key]}
            print(json.dumps(native,sort_keys=True))
        else:
            raise ValueError('Unknown catalogue phase')
        return
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        keys=[item['key'] for item in frozen_report()['comparisons']['native_187']['columns']['changed']
              if item['properties'].get('not_null')==[True,False]]
        assert len(keys)==29
        plan=DEST/'original-required.json'
        plan.write_bytes(subprocess_output('plan',json.dumps(keys).encode()))
        os.chmod(plan,0o644)
        roots=[PACKET,CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(DB)]
        opts=dict(database=DB,directory=DEST,roots=roots)
        run('upgrade-contracts',['-u',MODULE+',step_document_library'],launcher=ROOT/'tools/load_cerro_catalog_contracts.py',**opts)
        census=module_census(DB)
        assert census['installed']==188 and not any(census[k] for k in ('non_free','enterprise','pending'))
        official=(DEST/'upgrade-contracts.log').read_text()
        drops=[line.split(' ',1)[1] for line in official.splitlines() if line.startswith('CERRO_RETAINED_REQUIRED ')]
        assert len(drops)==1 and set(json.loads(drops[0]))==set(json.loads(plan.read_bytes())['fields'])
        fruit=verify(DB,DEST,roots)
        assert fruit['native_sha256']==fruit['target_sha256'] and not fruit['changes']
        # The CLI in the preceding phase did not write a single deleted or replaced original row.
        assert all_guards(DB)==all_guards(FINAL_TARGET) and guard('verify',DB)==guard('verify',FINAL_TARGET)
        assert directory(DB)==directory(FINAL_TARGET)
        body = 'import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        body += "from probe_cerro_fruit_assignments import exercise as assignments\n"
        body += "from probe_cerro_export_contacts import capture,exercise\n"
        body += "users=assignments(env)\ncontacts=capture(env)\nexercise(env)\nassert capture(env)==contacts\n"
        body += "print('CERRO_CATALOGUE_USERS', json.dumps(dict(users=users,contacts=contacts),sort_keys=True))"
        source_ops=native_read(body,'catalogue-edits','CERRO_CATALOGUE_USERS')
        run('catalogue-edits',[],body,**opts)
        target_ops=receipt(DEST/'catalogue-edits.log','CERRO_CATALOGUE_USERS')
        assert target_ops==source_ops
        rows=json.loads(subprocess_output('rows'))
        raw=subprocess_output('result')
        (DEST/'schema-final.json').write_bytes(raw)
        report=json.loads(raw)
        diff=report['comparisons']['native_corrected']
        assert not any(obj['removed'] for obj in diff.values())
        assert not diff['columns']['changed'] and not diff['views']['changed']
        assert not diff['odoo_access']['changed'] and not diff['odoo_rules']['changed']
        for section in ('odoo_group_users','odoo_group_inheritance','odoo_view_groups','odoo_menu_groups','odoo_field_groups'):
            assert not diff[section]['changed']
        assert {item['key'][2] for item in diff['constraints']['changed']}==set(fruit['equivalent_checks'])
        for section in ('indexes','types','relations'):
            for item in diff[section]['changed']:
                for name,(old,new) in item['properties'].items():
                    assert name in ('owner','grants') and json.dumps(old).replace('cerro_odoo18','dev_odoo18')==json.dumps(new)
        summary=dict(census=census,physical_sha256=hashlib.sha256(raw).hexdigest(),fruit=fruit,
                     retained_on_upgrade=json.loads(drops[0]),historical_rows=rows,
                     user_operations=source_ops['users'],contact_contexts=len(source_ops['contacts']),
                     native={name:{'source':entry['source'],'target':entry['target']} for name,entry in diff.items()})
        (DEST/'accepted-contracts.json').write_text(json.dumps(summary,sort_keys=True))


if __name__=='__main__':
    main()
