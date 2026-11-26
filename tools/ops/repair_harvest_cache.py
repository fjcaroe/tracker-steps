"""Repair only Harvest shell cache validators; keep certified web/backend bytes.

An isolated nginx fixture reproduces old-browser revalidation before deployment.
No Odoo writes, browser storage deletion, service-worker removal or app upgrade.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess

from publish_harvest_web import CONFIGS, HOSTS, patch_config, validate, public_hashes, verify_shell_revalidation

RELEASES={'0.0.3':'d7e8e5866577236bd11af62750cba7d121fbeafd',
          '0.0.5':'e14075aaef7a9e71448e087b52bd80e9cebacff0',
          '0.0.11':'680e694cd0320c90366327a31e3f9475ab6f4cbb'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_config(stage, fixed):
    state=json.loads((stage/'state.json').read_text())
    source='server { listen 443 ssl; server_name fixture.invalid;\nlocation = /cosecha { return 301 /cosecha/; }\nlocation ^~ /cosecha/ { alias /unused/; }\n}'
    server=patch_config(source,'fixture.invalid',stage/'current/app')
    server=server.replace('listen 443 ssl;',f'listen 127.0.0.1:{state["port"]};')
    if not fixed:
        server=server.replace('etag off;','').replace('if_modified_since off;','').replace('"no-store"','"no-cache"')
    return ('pid '+str(stage/'nginx.pid')+';\nerror_log '+str(stage/'error.log')+';\n'
            'events {}\nhttp { include /etc/nginx/mime.types; access_log '+str(stage/'access.log')+';\n'+server+'\n}\n')


def fixture(args):
    stage=args.stage.resolve()
    assert str(stage).startswith('/opt/steps-validation/harvest-cache-fixture-') and len(stage.parts)==4
    if args.action=='fixture-start':
        stage.mkdir(mode=0o755,exist_ok=False)
        with socket.socket() as listener:listener.bind(('127.0.0.1',args.port))
        (stage/'state.json').write_text(json.dumps({'port':args.port,'policy_sha256':sha(Path(__file__).with_name('publish_harvest_web.py'))}))
        (stage/'current').symlink_to(Path('/var/www/steps-harvest-releases/cerro')/RELEASES['0.0.3'],target_is_directory=True)
        (stage/'nginx.conf').write_text(fixture_config(stage,False))
        subprocess.run(['nginx','-t','-p',str(stage),'-c',str(stage/'nginx.conf')],check=True)
        subprocess.run(['nginx','-p',str(stage),'-c',str(stage/'nginx.conf')],check=True)
    elif args.action=='fixture-switch':
        assert (stage/'current').is_symlink() and (stage/'nginx.pid').exists()
        target=Path('/var/www/steps-harvest-releases/cerro')/RELEASES[args.version]
        validate(target)
        next_link=stage/'next';assert not next_link.exists()
        next_link.symlink_to(target,target_is_directory=True);next_link.replace(stage/'current')
        (stage/'nginx.conf').write_text(fixture_config(stage,args.fixed))
        subprocess.run(['nginx','-t','-p',str(stage),'-c',str(stage/'nginx.conf')],check=True)
        subprocess.run(['nginx','-p',str(stage),'-c',str(stage/'nginx.conf'),'-s','reload'],check=True)
    else:
        assert (stage/'nginx.pid').exists()
        subprocess.run(['nginx','-p',str(stage),'-c',str(stage/'nginx.conf'),'-s','quit'],check=True)
    print('HARVEST_CACHE_FIXTURE_OK '+args.action)


def deploy(args):
    stage=args.stage.resolve()
    assert str(stage).startswith('/opt/steps-validation/harvest-cache-') and len(stage.parts)==4
    assert 'fixture' not in stage.name
    stage.mkdir(mode=0o700,exist_ok=False)
    reviewed=json.loads(args.review.read_text())
    policy=Path(__file__).with_name('publish_harvest_web.py')
    assert reviewed['policy_sha256']==sha(policy)
    assert {r['from'] for r in reviewed['cases']}=={'0.0.3','0.0.5'}
    assert all(r['stale_before_fix'] and r['to']=='0.0.11' and r['storage_preserved'] for r in reviewed['cases'])
    shutil.copy2(args.review,stage/'browser-rehearsal.json')
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX | fcntl.LOCK_NB)
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:argv=path.read_bytes().decode(errors='replace').split('\0')
            except OSError:continue
            if any(Path(a).name=='odoo-bin' for a in argv):
                assert not any(a in ('-u','-i','--update','--init') or a.startswith(('--update=','--init=')) for a in argv),'Concurrent upgrade'
        baseline={};manifests={};roots={}
        for environment in HOSTS:
            root=Path('/var/www/steps-harvest-releases')/environment/RELEASES['0.0.11']
            manifest=validate(root);assert manifest['version']=='0.0.11'
            manifests[environment]=manifest;roots[environment]=root
            config=Path(CONFIGS[environment]).resolve();source=config.read_text()
            aliases=re.findall(r'alias\s+(/var/www/steps-harvest-releases/'+re.escape(environment)+r'/[a-f0-9]{40}/app)(?:/|;)',source)
            assert aliases and set(aliases)=={str(root/'app')},'Unexpected published build'
            passed=Path('/opt/steps-validation')/('management_'+environment+'_t243_179a6daa')
            certificate=json.loads((passed/'qa_passed.json').read_text())
            delivery=json.loads((passed/'harvest-web-deployed.json').read_text())
            assert delivery['web_commit']==manifest['commit'] and delivery['served']==manifest['files']
            assert delivery['backend_commit']==certificate['commit']
            baseline[environment]={'path':config,'source':source,'sha256':sha(config),
                'replacement':patch_config(source,HOSTS[environment],root/'app')}
        assert manifests['development']==manifests['cerro']==manifests['qa-cerro']
        for environment,item in baseline.items():
            shutil.copy2(item['path'],stage/(environment+'-nginx-before.conf'))
            (stage/(environment+'-nginx-after.conf')).write_text(item['replacement'])
        subprocess.run(['nginx','-t'],check=True)
        results={};changed=[]
        try:
            # Development review is complete before either customer vhost changes.
            for environment in ('development','qa-cerro','cerro'):
                item=baseline[environment]
                assert sha(item['path'])==item['sha256'],'Concurrent nginx change'
                assert validate(roots[environment])==manifests[environment],'Concurrent static change'
                item['path'].write_text(item['replacement']);changed.append(environment)
                subprocess.run(['nginx','-t'],check=True)
                subprocess.run(['systemctl','reload','nginx'],check=True)
                # Wait for worker handover via the existing bounded hash checker.
                served=public_hashes(HOSTS[environment],manifests[environment],attempts=20)
                conditions=verify_shell_revalidation(HOSTS[environment],manifests[environment])
                results[environment]={'version':'0.0.11','commit':RELEASES['0.0.11'],'served':served,
                    'conditional_requests':conditions,'nginx_before_sha256':item['sha256'],
                    'nginx_after_sha256':sha(item['path'])}
        except BaseException:
            for environment in changed:
                item=baseline[environment]
                assert item['path'].read_text()==item['replacement'],'Unexpected config change; preserve it'
                item['path'].write_text(item['source'])
            subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
            raise
        proof={'results':results,'policy_sha256':sha(policy),'tool_sha256':sha(Path(__file__)),
               'web_files_unchanged':True,'odoo_writes':False,'storage_cleared':False,
               'backup':str(stage),'verified_at':datetime.now(timezone.utc).isoformat()}
        (stage/'delivery.json').write_text(json.dumps(proof,indent=2))
        print('HARVEST_CACHE_REPAIRED '+json.dumps({'versions':{e:v['version'] for e,v in results.items()},'backup':str(stage)}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('fixture-start','fixture-switch','fixture-stop','deploy'))
    parser.add_argument('--stage',required=True,type=Path)
    parser.add_argument('--port',type=int,default=18471)
    parser.add_argument('--version',choices=tuple(RELEASES),default='0.0.11')
    parser.add_argument('--fixed',action='store_true')
    parser.add_argument('--review',type=Path)
    args=parser.parse_args();assert os.geteuid()==0
    if args.action.startswith('fixture-'):fixture(args)
    else:deploy(args)


if __name__=='__main__':main()
