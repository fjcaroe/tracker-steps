"""Restore the sealed native Cerro corpus and exercise the expanded Studio owners on a fresh private database."""
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile

from check_cerro_studio_strict import ROOT, tree_sha
from compare_cerro_studio_strict import NATIVE
from restore_cerro_studio_strict import SPACE, references, sql
from verify_cerro_native_catalog_graph import SOURCE, season_contract, estimate_contract, categories

TARGET = 'MANAGEMENT_QA_CERRO_BOM_20261126U42N'
TRIAL = NATIVE / 'native-catalog-graph-u42n'
SQL = NATIVE / 'cerro-control.dump'
FILESTORE = Path('/opt/steps-validation/community-product-custody-20261126U40/cerro-20261126U40Q/filestore.tar')
OWNERS = ('step_cerro_bom_company','step_cerro_product_account_views','step_cerro_studio_farms',
          'step_cerro_studio_agriculture','step_cerro_studio_budgets','step_cerro_studio_companies',
          'step_cerro_studio_exports','step_cerro_studio_packing','step_cerro_studio_process_types',
          'step_cerro_studio_producers','step_cerro_studio_species','step_cerro_studio_transfers')
PROVIDERS = ('step_agriculture_core','step_agriculture_catalogs','step_agriculture_shared_farms',
             'step_management_costs_agriculture','step_packing','step_producers')


def pg(*args, source=None):
    subprocess.run(['runuser','-u','postgres','--',*args],stdin=source,check=True,stdout=subprocess.DEVNULL)


def restore():
    if (TRIAL/'restored.json').is_file():
        return
    if sql('postgres',f"SELECT count(*) FROM pg_database WHERE datname='{TARGET}'") != '0':
        raise ValueError('Existing trial database without its restore receipt')
    for path, digest in ((SQL,'954c632423424cc31923e9ec5b8f01f5944435491cec4da11b69e8e02f1654b7'),
                         (FILESTORE,'b2e8884bb67a26d37c742f740ed061328dcdefab901f184d0f205fb424175efe')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert shutil.disk_usage('/var/lib/postgresql/12/main').free > 5*1024**3
    assert shutil.disk_usage('/opt').free > 8*1024**3
    available = next(l for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
    assert int(available.split()[1]) > 1572864
    pg('createdb','--template=template0','--tablespace='+SPACE,'--owner=cerro_odoo18',TARGET)
    with SQL.open('rb') as source:
        pg('pg_restore','--no-tablespaces','--exit-on-error','--single-transaction','--dbname='+TARGET,source=source)
    objects = references(TARGET)
    assert len(objects)==676 and references(SOURCE)==objects
    data = TRIAL/'data'
    destination = data/'filestore'/TARGET
    destination.mkdir(parents=True,mode=0o750)
    with tarfile.open(FILESTORE) as archive:
        members = archive.getmembers()
        assert len(members)==len(objects) and {m.name for m in members}==objects.keys()
        for m in members:
            checksum, size = objects[m.name]
            assert m.isfile() and m.size==size
            content=archive.extractfile(m).read()
            assert hashlib.sha1(content).hexdigest()==checksum
            target=destination/m.name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
    actor=pwd.getpwnam('cerro_odoo18')
    for file in (data,*data.rglob('*')):
        os.chown(file,actor.pw_uid,actor.pw_gid)
        file.chmod(0o750 if file.is_dir() else 0o640)
    assert estimate_contract(SOURCE)==estimate_contract(TARGET) and categories(SOURCE)==categories(TARGET)
    assert season_contract(SOURCE)==season_contract(TARGET)
    (TRIAL/'restored.json').write_text(json.dumps({'objects':len(objects),'bytes':sum(s for _,s in objects.values())}))


def guard(mode,file):
    with (TRIAL/file).open('w') as out:
        subprocess.run(['runuser','-u','postgres','--','/usr/bin/python3.10',str(ROOT/'tools/guard_cerro_studio_upgrade.py'),
                        '--database',TARGET,'--mode',mode],stdout=out,check=True)


def main():
    with open('/run/lock/steps-environments.lock','rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        from derive_cerro_native_catalog_order import derive_core
        config=configparser.ConfigParser(interpolation=None)
        config.read('/etc/odoo18-cerroelplomo.conf')
        original_paths=[Path(p.strip()) for p in config['options']['addons_path'].split(',')]
        legacy=next(p/'step_hr' for p in original_paths if (p/'step_hr/__manifest__.py').is_file())
        native_core=TRIAL/'sources/step_agriculture_core'
        if not native_core.exists():
            evidence=derive_core(ROOT/'native-catalog-graph-6f4f9509a18a/step_agriculture_core',legacy,native_core)
            (TRIAL/'native-core-source.json').write_text(json.dumps(evidence,sort_keys=True))
        assert tree_sha(native_core)==json.loads((TRIAL/'native-core-source.json').read_text())['native_core']
        species=ROOT/'view-alias-add2d259eb/step_agriculture_species_pallet'
        digest='d25b9ac8bfb41771b7d05b5b287c277b32ea0517dc17af21ddccf78502741b30'
        assert tree_sha(species)==digest
        destination=TRIAL/'sources'/species.name
        if not destination.exists():
            shutil.copytree(species,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        assert tree_sha(destination)==digest
        restore()
        guard('arm','before.json')
        config=Path('/etc/odoo18-cerroelplomo.conf')
        source=configparser.ConfigParser(interpolation=None)
        source.read(config)
        paths=[TRIAL/'sources',NATIVE/'native-catalog-graph-v3/providers',ROOT/'process-catalog-4f7fbac81c90',
               ROOT/'native-catalog-graph-6f4f9509a18a',ROOT/'bom-restore-2d6b0a1c73e6',
               NATIVE/'native-directory-v1/views',NATIVE/'native-directory-v1/core',NATIVE/'upgrade-final-v2/addons',
               NATIVE/'free-sibling-fields/addons',NATIVE/'process-16468b136f/addons',NATIVE/'species-278a413917/addons',
               NATIVE/'farm-c0ede82757/addons',NATIVE/'final-views', NATIVE/'addons']
        assert all(p.is_dir() for p in paths)
        runner=['unshare','--net','runuser','-u','cerro_odoo18','--','/usr/bin/python3.10','/opt/odoo18/odoo-bin']
        options=['-c',str(config),'-d',TARGET,'--db-filter=^'+TARGET+'$','--db_host=/var/run/postgresql',
                 '--data-dir='+str(TRIAL/'data'),'--logfile='+str(TRIAL/'data/odoo.log'),'--without-demo=all',
                 '--workers=0','--max-cron-threads=0','--load=base,web','--no-http','--stop-after-init',
                 '--addons-path='+','.join(map(str,paths))+','+source['options']['addons_path']]
        for name,cmd in [('install',['-i',','.join(OWNERS),'-u',','.join(PROVIDERS)]),
                         ('upgrade',['-u',','.join([*OWNERS,*PROVIDERS])])]:
            with (TRIAL/(name+'.log')).open('wb') as log:
                subprocess.run(runner+options+cmd,stdout=log,stderr=log,check=True)
            assert estimate_contract(SOURCE)==estimate_contract(TARGET) and categories(SOURCE)==categories(TARGET)
            guard('verify','after.json')
        with (TRIAL/'postflight.py').open('rb') as code,(TRIAL/'postflight.log').open('wb') as log:
            subprocess.run(runner+['shell']+options,stdin=code,stdout=log,stderr=log,check=True)
        from verify_cerro_native_catalog_graph import verify
        result=verify(TRIAL,TARGET)
        (TRIAL/'verified.json').write_text(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
