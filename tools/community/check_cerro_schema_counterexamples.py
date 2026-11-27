"""Prove the effect of Cerro's restored fruit rules, package weight and accounting constraints."""
import configparser
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from decimal import Decimal

import psycopg2
from psycopg2 import sql

from check_cerro_combined_budget import BUDGET, PACKAGE
from check_cerro_export_contacts import CONTACTS
from check_cerro_freight_directory import FREIGHT
from check_cerro_studio_strict import ROOT, addon_roots, run
from compare_cerro_studio_receipts import receipt
from restore_cerro_bom_before_guard import FINAL_DEST, FINAL_TARGET
from restore_cerro_native_catalog_graph import TRIAL as NATIVE, TARGET as NATIVE_DB
from restore_cerro_studio_strict import SOURCE

from cerro_accounting_checks import CHECKS,ELEM,ARRAY
NATIVE_SOURCE='MANAGEMENT_QA_CERRO_CUSTODY_20261126U40Q'


def physical(db):
    with psycopg2.connect(dbname=db,host='/var/run/postgresql') as connection:
        connection.set_session(readonly=True,isolation_level='REPEATABLE READ')
        with connection.cursor() as cr:
            cr.execute("SET LOCAL search_path=pg_catalog,public")
            cr.execute("SELECT id,base_weight FROM stock_package_type ORDER BY id")
            weights={k: (None if v is None else Decimal.from_float(v) if isinstance(v,float) else v) for k,v in cr}
            cr.execute("SELECT conname,pg_get_constraintdef(oid,false) FROM pg_constraint "
                       "WHERE conrelid='account_move_line'::regclass AND conname=ANY(%s)",(list(CHECKS),))
            checks=dict(cr.fetchall())
            cr.execute(sql.SQL('SELECT ({}) IS NOT DISTINCT FROM ({})').format(sql.SQL(ELEM),sql.SQL(ARRAY)))
            assert cr.fetchone()==(True,)
            usage={}
            for table,field in [('account_move_line','account_id'),('purchase_order_line','product_uom'),
                                ('product_pricelist_item','uom_id')]:
                cr.execute(sql.SQL('SELECT count({}),count(DISTINCT {}) FROM {}').format(
                    sql.Identifier(field),sql.Identifier(field),sql.Identifier(table)))
                usage[table+'.'+field]=cr.fetchone()
            return weights,checks,usage


def count_physical(target):
    old,source_checks,usage=physical(NATIVE_SOURCE)
    new,target_checks,target_usage=physical(target)
    assert old.keys()==new.keys() and len(old)==6 and source_checks.keys()==target_checks.keys()==set(CHECKS)
    altered=[]
    for name in CHECKS:
        before,after=source_checks[name],target_checks[name]
        if before==after:
            continue
        if before.count(ELEM)!=1 or after.count(ARRAY)!=1 or before.replace(ELEM,'ITEMS')!=after.replace(ARRAY,'ITEMS'):
            raise ValueError('Unclassified check predicate '+name)
        altered.append(name)
    return {'weight_rows':len(old),'weight_non_null':sum(v is not None for v in old.values()),
            'exact_decimal_changes':sum(v!=new[k] for k,v in old.items()),
            'equivalent_checks':altered,'origin_fk_references':usage,'target_fk_references':target_usage}


def native_read(body, phase='fruit-schema', label='FRUIT_SCHEMA'):
    config=Path('/etc/odoo18-cerroelplomo.conf')
    parser=configparser.ConfigParser(interpolation=None)
    parser.read(config)
    source=json.loads((ROOT/'tools/cerro_native_providers_receipt.json').read_text())
    paths=','.join(str(Path('/opt/steps-validation')/p) for p in source['roots'])
    options=['-c',str(config),'-d',NATIVE_DB,'--db-filter=^'+NATIVE_DB+'$','--db_host=/var/run/postgresql',
             '--data-dir='+str(NATIVE/'data'),'--logfile='+str(NATIVE/'data'/(phase+'.log')),
             '--without-demo=all','--workers=0','--max-cron-threads=0','--load=base,web','--no-http',
             '--stop-after-init','--addons-path='+paths+','+parser['options']['addons_path']]
    dst=NATIVE/('original-'+phase+'.log')
    with dst.open('w') as out:
        subprocess.run(['unshare','--net','runuser','-u','cerro_odoo18','--','/usr/bin/python3.10',
                        '/opt/odoo18/odoo-bin','shell',*options],input=body,text=True,stdout=out,stderr=out,check=True)
    return receipt(dst,label)


def verify(db,dest,roots):
    body='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
    body+="from probe_cerro_fruit_schema import capture\nprint('FRUIT_SCHEMA',json.dumps(capture(env),sort_keys=True))"
    native=native_read(body)
    run('original-fruit-schema',[],body,database=db,directory=dest,roots=roots)
    current=receipt(dest/'original-fruit-schema.log','FRUIT_SCHEMA')
    assert current.keys()==native.keys()
    changes={}
    for name,partitions in native.items():
        assert partitions.keys()==current[name].keys()
        for company,ids in partitions.items():
            old,new=set(ids),set(current[name][company])
            if old!=new:
                changes.setdefault(name,{})[company]={'lost':len(old-new),'gained':len(new-old)}
    cod='import json,sys;sys.path.insert(0,sys.argv[1]);from check_cerro_schema_counterexamples import count_physical;print(json.dumps(count_physical(sys.argv[2]),sort_keys=True))'
    facts=json.loads(subprocess.check_output(['runuser','-u','postgres','--','/usr/bin/python3.10','-c',cod,str(ROOT/'tools'),db],text=True))
    facts.update(actor=6,models=len(native),contexts=len(next(iter(native.values()))),
                 changes=changes,native_sha256=hashlib.sha256(json.dumps(native,sort_keys=True).encode()).hexdigest(),
                 target_sha256=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest())
    (dest/'schema-counterexamples.json').write_text(json.dumps(facts,sort_keys=True))
    return facts


if __name__=='__main__':
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_SH)
        verify(FINAL_TARGET,FINAL_DEST,[CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(FINAL_TARGET)])
