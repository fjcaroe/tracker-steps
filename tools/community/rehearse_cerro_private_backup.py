"""Recover a sealed Cerro PG12 pilot into its own local cluster and compare every table, sequence and object."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import subprocess
import tarfile

import psycopg2
from psycopg2 import sql

from backup_cerro_catalog_pilots import inventory,PILOTS


def archive_files(root,db):
    files={}
    for name in ('dump','filestore','inventory'):
        item=root/(db+'-'+name)
        seal=json.loads(item.with_suffix('.json').read_bytes())
        assert seal['database']==db and seal['artifact']==name and seal['bytes']==item.stat().st_size
        assert hashlib.sha256(item.read_bytes()).hexdigest()==seal['sha256']
        files[name]=item
    return files


def restore(db,artifacts,dest,socket,port,pg):
    assert db in PILOTS and port==55442 and socket.resolve()==Path('/work/cerro-pg/socket')
    opts=dict(host=str(socket),port=port,user='postgres')
    with psycopg2.connect(dbname='postgres',**opts) as conn:
        conn.autocommit=True
        with conn.cursor() as cr:
            cr.execute("SELECT current_setting('server_version'),current_user,current_setting('listen_addresses')")
            version,user,listen=cr.fetchone()
            assert version.startswith('12.22') and user=='postgres' and listen==''
            cr.execute("SELECT 1 FROM pg_roles WHERE rolname='dev_odoo18'")
            if not cr.fetchone():
                cr.execute('CREATE ROLE dev_odoo18 LOGIN NOSUPERUSER')
    files=archive_files(artifacts,db)
    incoming=json.loads(files['inventory'].read_bytes())
    dest.mkdir(parents=True,exist_ok=True)
    marker=dest/'restore-start.json'
    claim=dict(database=db,archive_sha256=hashlib.sha256(files['dump'].read_bytes()).hexdigest())
    dbprefix=[str(pg/'psql'),'-XAt','-h',str(socket),'-p',str(port),'-U','postgres','-d','postgres','-c']
    owner=subprocess.check_output(dbprefix+["SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+db+"'"],text=True).strip()
    if not marker.exists():
        if owner:
            raise ValueError('The requested local database already exists outside this restore')
        marker.write_text(json.dumps(claim,sort_keys=True))
    assert json.loads(marker.read_bytes())==claim
    if not owner:
        subprocess.run([str(pg/'createdb'),'-h',str(socket),'-p',str(port),'-U','postgres','--owner=dev_odoo18',
                        '--template=template0','--encoding=UTF8','--lc-collate=C.UTF-8','--lc-ctype=C.UTF-8',db],check=True)
    else:
        assert owner=='dev_odoo18'
    with psycopg2.connect(dbname=db,**opts) as conn,conn.cursor() as cr:
        cr.execute("SELECT to_regclass('public.ir_model')")
        empty=cr.fetchone()[0] is None
    if empty:
        subprocess.run([str(pg/'pg_restore'),'-h',str(socket),'-p',str(port),'-U','postgres','--single-transaction',
                        '--exit-on-error','--no-tablespaces','-d',db,str(files['dump'])],check=True)
    # The caller executes inside the isolated QA userspace as the postgres OS
    # user so this explicit socket is the only server the inventory can reach.
    result=inventory(db,str(socket),port)
    result=json.loads(json.dumps(result))
    changes=[]
    if result['sections']['constraints']!=incoming['sections']['constraints']:
        from cerro_backup_constraints import verify_deparse
        origin='COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M' if db.endswith('U44K') else db
        data=json.loads(gzip.decompress((artifacts/(origin+'-constraints.gz')).read_bytes()))
        constraints=result['sections']['constraints']
        assert constraints[0]==incoming['sections']['constraints'][0]
        changes=verify_deparse(data,db,socket,port,incoming['sections']['constraints'][1],constraints[1])
        # Retain the raw digest and the named predicate proof in the receipt.
        result['sections']['constraints']=incoming['sections']['constraints']
    else:
        constraints=result['sections']['constraints']
    if result!=incoming:
        changed={section:[key for key in incoming[section] if incoming[section][key]!=result[section].get(key)]
                 for section in incoming}
        (dest/'catalogue-differences.json').write_text(json.dumps(changed,sort_keys=True))
        raise AssertionError({section:keys[:6] for section,keys in changed.items() if keys})
    filestore=dest/'data/filestore'/db
    filestore.mkdir(parents=True,exist_ok=True)
    remaining=set(incoming['objects'])
    with tarfile.open(files['filestore']) as archive:
        for member in archive:
            assert member.isfile() and member.name in remaining
            sha,size=incoming['objects'][member.name]
            assert member.name==sha[:2]+'/'+sha and member.size==size
            data=archive.extractfile(member).read()
            assert hashlib.sha1(data).hexdigest()==sha
            path=filestore/member.name
            assert not path.is_symlink() and not path.parent.is_symlink()
            path.parent.mkdir(exist_ok=True)
            if not path.exists():
                with path.open('xb') as output:
                    output.write(data)
                path.chmod(0o600)
            assert path.read_bytes()==data
            remaining.remove(member.name)
    assert not remaining
    final=dict(database=db,archive=claim['archive_sha256'],inventory=hashlib.sha256(files['inventory'].read_bytes()).hexdigest(),
               tables=len(result['tables']),rows=sum(row[0] for row in result['tables'].values()),
               sequences=len(result['sequences']),catalogue_sections=len(result['sections']),objects=len(result['objects']),
               local_constraints_sha256=constraints[1],equivalent_check_constraints=changes)
    (dest/'recovered.json').write_text(json.dumps(final,sort_keys=True))
    print(json.dumps(final,sort_keys=True))


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--database',choices=PILOTS,required=True)
    cli.add_argument('--artifacts',type=Path,required=True)
    cli.add_argument('--dest',type=Path,required=True)
    cli.add_argument('--socket',type=Path,required=True)
    cli.add_argument('--pg-bin',type=Path,default=Path('/usr/lib/postgresql/12/bin'))
    args=cli.parse_args()
    restore(args.database,args.artifacts,args.dest,args.socket,55442,args.pg_bin)
