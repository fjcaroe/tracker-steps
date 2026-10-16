"""Prepare the private AIS receiver; enable only after a key is provisioned.

Requires the tested step_export_control addon to be installed first. No key is
created, modified, printed, committed or requested over RPC by this installer.
"""
import argparse
import fcntl
import os
from pathlib import Path
import shutil
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'))
p.add_argument('--enable',action='store_true')
a=p.parse_args()
assert os.geteuid()==0
with open('/run/lock/steps-environments.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    source=Path(__file__).resolve().parent
    destination=Path('/opt/steps-managed/aisstream')
    destination.mkdir(parents=True,exist_ok=True)
    for name in ('aisstream_collector.py','environments.json'):
        shutil.copy2(source/name,destination/name)
    private=Path('/etc/steps/aisstream.env')
    private.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if not private.exists():
        private.write_text('# Private AISStream key; provision locally, never in Git.\nAISSTREAM_API_KEY=\n')
        private.chmod(0o600)
    service='odoo18-dev.service' if a.environment=='development' else 'odoo18-cerroelplomo.service'
    user=subprocess.check_output(['systemctl','show','--value','--property=User',service],text=True).strip()
    unit='steps-aisstream-'+a.environment+'.service'
    text=f'''[Unit]
Description=Steps AISStream {a.environment}
After=network-online.target {service}
Wants=network-online.target

[Service]
Type=simple
User={user}
EnvironmentFile=/etc/steps/aisstream.env
ExecStart=/usr/bin/python3.10 /opt/steps-managed/aisstream/aisstream_collector.py {a.environment}
Restart=on-failure
RestartSec=30
NoNewPrivileges=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=multi-user.target
'''
    Path('/etc/systemd/system',unit).write_text(text)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    if a.enable:
        values=dict(line.strip().split('=',1) for line in private.read_text().splitlines() if '=' in line and not line.startswith('#'))
        assert values.get('AISSTREAM_API_KEY','').strip(),'Provision the private key before enabling AIS'
        subprocess.run(['systemctl','enable','--now',unit],check=True)
    print('AIS_SERVICE_READY environment='+a.environment+' enabled='+str(a.enable))
