"""Repair only asset timestamps of an already verified private release.

File bytes must match its immutable manifest before and after. Probe a passed
target copy first; --live restarts only the explicitly selected target service.
"""
import argparse,configparser,fcntl,hashlib,json,os,pwd,re,subprocess
from datetime import datetime,timezone
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'))
p.add_argument('commit')
p.add_argument('timestamp',type=int)
p.add_argument('--run-id',required=True)
p.add_argument('--live',action='store_true')
a=p.parse_args()
assert os.geteuid()==0 and re.fullmatch('[0-9a-f]{40}',a.commit) and re.fullmatch('[a-z0-9_]{1,24}',a.run_id)
assert 1600000000<a.timestamp<=datetime.now(timezone.utc).timestamp()
target=json.loads(Path(__file__).with_name('environments.json').read_text())['environments'][a.environment]
stage=Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.run_id)
passed=json.loads((stage/'qa_passed.json').read_text())
assert passed['commit']==a.commit
root=Path('/opt/steps-managed/releases')/a.environment/a.commit if a.live else stage/'addons'
proof=json.loads((root/'release.json').read_text())
assert proof['commit']==a.commit
cfg=configparser.ConfigParser(interpolation=None);cfg.read(target['config'])
user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
database=target['database'] if a.live else passed['database']

def check_bytes():
    for name,expected in proof['files'].items():
        path=(root/name).resolve()
        assert path.is_relative_to(root.resolve()) and hashlib.sha256(path.read_bytes()).hexdigest()==expected

def checksum():
    code="try:\n print('ASSET_CHECKSUM '+env['ir.qweb']._get_asset_bundle('web.assets_web').get_checksum('js'))\nfinally:env.cr.rollback()\n"
    command=['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],
        '-d',database,'--no-http','--workers=0','--max-cron-threads=0',
        '--addons-path='+str(root)+','+cfg['options']['addons_path'],
        '--logfile=/tmp/steps-asset-metadata-'+a.environment+'.log']
    result=subprocess.run(command,input=code,text=True,capture_output=True)
    found=re.search(r'ASSET_CHECKSUM ([a-f0-9]{64})',result.stdout)
    assert result.returncode==0 and found,result.stderr[-1200:]
    return found[1]

with open('/run/lock/steps-environments.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args=command.read_bytes().decode(errors='replace').split('\x00')
        except OSError:
            continue
        if any(Path(arg).name=='odoo-bin' for arg in args):
            assert not any(arg in ('-i','-u','--update','--init') or arg.startswith(('--update=','--init=')) for arg in args),'Concurrent Odoo upgrade'
    if a.live:
        copy=json.loads((stage/'asset_metadata_passed.json').read_text())
        assert copy['commit']==a.commit and copy['timestamp']==a.timestamp and copy['content_preserved']
    check_bytes()
    before=checksum()
    changed={}
    for name in proof['files']:
        path=root/name
        if '/static/' in name and path.suffix in ('.js','.xml','.css','.scss','.svg'):
            changed[name]=path.stat().st_mtime
            os.utime(path,(a.timestamp,a.timestamp))
    check_bytes()
    after=checksum()
    assert before!=after or all(t==a.timestamp for t in changed.values())
    report={'commit':a.commit,'environment':a.environment,'database':database,'root':str(root),
        'content_preserved':True,'previous_mtimes':changed,'timestamp':a.timestamp,'before_checksum':before,'after_checksum':after}
    if a.live:
        backup=Path('/opt/steps_backups')/('asset_metadata_'+a.environment+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700)
        (backup/'metadata.json').write_text(json.dumps(report,indent=2))
        subprocess.run(['systemctl','restart',target['service']],check=True)
        print('ASSET_METADATA_LIVE_OK '+json.dumps(report))
    else:
        (stage/'asset_metadata_passed.json').write_text(json.dumps(report))
        print('ASSET_METADATA_COPY_OK '+json.dumps(report))
