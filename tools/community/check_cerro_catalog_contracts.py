"""Restore the Cerro 187 copy and compare its source contracts in a new private database."""
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from check_cerro_combined_budget import guard, BUDGET, PACKAGE
from check_cerro_export_contacts import CONTACTS, directory
from check_cerro_freight_directory import FREIGHT
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from check_cerro_schema_counterexamples import NATIVE_SOURCE, verify
from restore_cerro_bom_before_guard import FINAL_DEST, FINAL_TARGET, all_guards
from restore_cerro_studio_strict import GIB, SPACE, copy_filestore, module_census, pg, references, sql

DB = 'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M'
DEST = Path('/opt/steps-validation/community-cerro-contracts-20261127U44M')
PACKET = ROOT / 'historical-catalog-c29cb57fd355'
MODULE = 'step_cerro_catalog_contracts'
AUDIT_SHA = '5591e7ba4330db5dec7e1349f72f53e9e012f94ac88840d2b7901cc0248504df'
USER_SHA = '6ef1b1cd7f5c489c7571dfe288aad9619207e0ae911050d360d0724c68792efa'


def frozen_report():
    audit = FINAL_DEST / 'schema-audit/schema-v2.json'
    actual = FINAL_DEST / 'schema-counterexamples.json'
    assert hashlib.sha256(audit.read_bytes()).hexdigest() == AUDIT_SHA
    assert hashlib.sha256(actual.read_bytes()).hexdigest() == USER_SHA
    return json.loads(audit.read_bytes())


def clone():
    DEST.mkdir(mode=0o751, exist_ok=True)
    marker = DEST / 'clone.json'
    start = DEST / 'started.json'
    identity = {'source': FINAL_TARGET, 'target': DB, 'tablespace': SPACE, 'audit_sha256': AUDIT_SHA}
    if marker.exists():
        assert json.loads(marker.read_bytes()) == identity
        return
    pgdir = Path(sql('postgres', 'SHOW data_directory'))
    space = Path(sql('postgres', "SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='" + SPACE + "'"))
    size = int(sql('postgres', "SELECT pg_database_size('" + FINAL_TARGET + "')"))
    memory = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))) * 1024
    assert space.resolve().is_relative_to('/opt/steps-validation')
    assert shutil.disk_usage(pgdir).free >= 5*GIB and shutil.disk_usage(space).free >= max(8*GIB, 3*size)
    assert memory >= 1536*1024**2
    if not start.exists():
        assert not sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + DB + "'")
        start.write_text(json.dumps(identity, sort_keys=True))
    assert json.loads(start.read_bytes()) == identity
    expected = module_census(FINAL_TARGET)
    assert expected['installed']==187 and not any(expected[k] for k in ('pending','non_free','enterprise'))
    if not sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + DB + "'"):
        pg('createdb','--owner=dev_odoo18','--tablespace='+SPACE,'--template='+FINAL_TARGET, DB)
    assert sql('postgres', "SELECT pg_get_userbyid(datdba)||'|'||spcname FROM pg_database JOIN pg_tablespace ON dattablespace=pg_tablespace.oid WHERE datname='"+DB+"'") == 'dev_odoo18|'+SPACE
    assert module_census(DB)==expected and all_guards(DB)==all_guards(FINAL_TARGET)
    assert guard('verify',DB)==guard('verify',FINAL_TARGET) and directory(DB)==directory(FINAL_TARGET)
    objects=references(FINAL_TARGET)
    assert references(DB)==objects
    copy_filestore(FINAL_DEST/'data/filestore'/FINAL_TARGET,DEST,DB,objects)
    marker.write_text(json.dumps(identity, sort_keys=True))


def restore_required(audit):
    changed=audit['comparisons']['native_187']['columns']['changed']
    original=[item['key'] for item in changed if item['properties'].get('not_null')==[True,False]]
    assert len(original)==29
    program='''import json,sys,psycopg2
from psycopg2 import sql
native,target=sys.argv[1:]
with psycopg2.connect(dbname=native) as source, psycopg2.connect(dbname=target) as candidate:
 source.set_session(readonly=True)
 with source.cursor() as base,candidate.cursor() as cr:
  for schema,table,field in json.load(sys.stdin):
   lookup="SELECT a.attnotnull,format_type(a.atttypid,a.atttypmod),pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=t.oid AND d.adnum=a.attnum WHERE n.nspname=%s AND t.relname=%s AND a.attname=%s AND NOT a.attisdropped"
   base.execute(lookup,(schema,table,field))
   required,typ,default=base.fetchone()
   cr.execute(lookup,(schema,table,field))
   observed=cr.fetchone()
   assert required is True and (typ,default)==observed[1:]
   relation=sql.Identifier(schema,table)
   column=sql.Identifier(field)
   cr.execute(sql.SQL('SELECT count(*) FROM {} WHERE {} IS NULL').format(relation,column))
   assert cr.fetchone()==(0,)
   if not observed[0]:
    cr.execute(sql.SQL('ALTER TABLE {} ALTER COLUMN {} SET NOT NULL').format(relation,column))
'''
    subprocess.run(['runuser','-u','postgres','--','/usr/bin/python3.10','-c',program,NATIVE_SOURCE,DB],
                   input=json.dumps(original),text=True,check=True)
    return original


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        audit=frozen_report()
        clone()
        assert tree_sha(PACKET/MODULE)=='1e4a354857d496bbf7c1afd3b2a8188028ccccbfd703a7251d43f4ce524f2629'
        roots=[PACKET,CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(DB)]
        opts=dict(database=DB,directory=DEST,roots=roots)
        run('adopt-catalogues',['-i',MODULE],**opts)
        state=sql(DB,"SELECT state FROM ir_module_module WHERE name='"+MODULE+"'")
        assert state=='installed'
        restore_required(audit)
        user=verify(DB,DEST,roots)
        assert not user['changes'] and user['native_sha256']==user['target_sha256']
        assert all_guards(DB)==all_guards(FINAL_TARGET) and guard('verify',DB)==guard('verify',FINAL_TARGET)
        assert directory(DB)==directory(FINAL_TARGET)


if __name__=='__main__':
    main()
