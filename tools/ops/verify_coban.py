"""Read-only effective-code/service/config checks; never prints keys or identifiers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert os.geteuid()==0
    proof=json.loads((a.stage/'deployment.json').read_text());qa=json.loads((a.stage/'qa.json').read_text())
    assert proof['commit']==qa['commit'] and proof['sha256']==qa['sha256'] and qa['tests']==22 and qa['copy_flow']
    actual=Path('/opt/steps-coban/current').resolve();assert actual.name==proof['commit']
    def files(root):
        return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert files(actual/'receivers')==files(a.stage/'source/receivers')
    assert Path('/etc/systemd/system/steps-coban.service').read_bytes()==(actual/'receivers/coban/steps-coban.service').read_bytes()
    for service in ('steps-coban.service','teltonika-ingest.service','tracker-steps-api.service','odoo18-cerroelplomo.service'):
        subprocess.run(['systemctl','is-active','--quiet',service],check=True)
    subprocess.run(['systemctl','is-enabled','--quiet','steps-coban.service'],check=True)
    identity=pwd.getpwnam('steps-coban')
    for name in ('config.json','devices.json','bridge-key.json'):
        info=(Path('/etc/steps-coban')/name).stat()
        assert info.st_uid==0 and info.st_gid==identity.pw_gid and info.st_mode&0o777==0o640
    result=subprocess.check_output(['sudo','-u','steps-coban','/usr/bin/python3.10','-m','receivers.coban.server','--config','/etc/steps-coban/config.json','--status'],cwd=actual,text=True)
    state=json.loads(result);assert state['registered_identities']==0 and state['queued']==0 and state['delivered_retained']==0
    operator=os.environ['SUDO_USER']
    rule=json.loads(subprocess.check_output(['sudo','-u',operator,'gcloud','compute','firewall-rules','describe','steps-coban-cerro-tcp5001','--project=stepsconsulting','--format=json'],text=True))
    assert not rule['disabled'] and rule['allowed']==[{'IPProtocol':'tcp','ports':['5001']}] and rule['targetTags']==['steps-coban-cerro']
    output={**proof,'tests':qa['tests'],'copy_flow':True,'effective_code_matches':True,'services_active':True,'autostart':True,'config_permissions_verified':True,'state':state,'firewall_verified':True}
    a.output.write_text(json.dumps(output,indent=2));a.output.chmod(0o644)
    print('COBAN_LIVE_VERIFY_OK effective_code=True service=True firewall=True permissions=True registered=0')


if __name__=='__main__':main()
