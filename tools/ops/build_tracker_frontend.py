"""Build with the existing public frontend settings, never copying .env to QA."""
import argparse,os,subprocess
from pathlib import Path
from dotenv import dotenv_values

p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args()
source=a.source.resolve()
settings={}
for filename in ('.env','.env.production'):
    settings.update(dotenv_values(Path('/opt/fernando_odoo18/apis/tracker-steps')/filename))
env=dict(os.environ)
for key in ('VITE_GOOGLE_MAPS_API_KEY','VITE_API_BASE_URL','VITE_ODOO_PORTAL'):
    if settings.get(key) is not None:env[key]=settings[key]
assert env.get('VITE_GOOGLE_MAPS_API_KEY'),'Missing existing public Maps configuration'
assert not (source/'.env').exists() and not (source/'.env.production').exists()
subprocess.run(['npm','ci','--no-audit','--no-fund'],cwd=source,env=env,check=True)
subprocess.run(['npm','run','build'],cwd=source,env=env,check=True)
print('TRACKER_FRONTEND_BUILD_OK public_configuration_only=True')
