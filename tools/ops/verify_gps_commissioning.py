"""Read-only verification of the exact installed GPS commissioning package."""
import json
from pathlib import Path
import stat
import subprocess
import sys
from urllib.request import urlopen

sys.path.insert(0,str(Path(__file__).resolve().parent))
from deploy_gps_commissioning import API,BASE,query,sha,tree


def main():
    source=Path(sys.argv[1]).resolve()
    frontend=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else source
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    proof=json.loads((BASE/commit/'production.json').read_text())
    assert proof['commit']==commit and proof['api_exact']
    assert tree(API/'app')==tree(source/'backend/tracker_py/app')
    receiver=Path('/opt/steps-coban/current').resolve()
    assert receiver.name==commit
    assert tree(receiver/'receivers')==tree(source/'receivers')
    config=Path('/etc/steps-coban/config.json');cfg=json.loads(config.read_text())
    assert cfg['host']=='0.0.0.0' and cfg['port']==5001 and cfg['api']=='http://127.0.0.1:8000'
    assert cfg['mapping']=='/var/lib/steps-coban/devices.json'
    for path,mode in [(config,0o640),(Path(cfg['key_file']),0o640),(Path(cfg['mapping']),0o600)]:assert stat.S_IMODE(path.stat().st_mode)==mode
    assert query('tracker_steps',"SELECT bool_and(receiver_seen_at>now()-interval '30 seconds') FROM gps_tenants WHERE issuer='CERRO_EL_PLOMO'")=='t'
    expected=int(query('tracker_steps',"SELECT count(*) FROM gps_device_registrations r JOIN gps_tenants t ON t.id=r.tenant_id WHERE t.issuer='CERRO_EL_PLOMO' AND r.receiver_mode IN ('capture','forward')"))
    assert len(json.loads(Path(cfg['mapping']).read_text()))==expected
    for service in ('steps-coban','tracker-steps-api','teltonika-ingest','odoo18-cerroelplomo'):
        subprocess.run(['systemctl','is-active','--quiet',service],check=True)
    subprocess.run(['systemctl','is-enabled','--quiet','steps-coban'],check=True)
    import hashlib
    frontend_assets={str(p.relative_to(frontend/'dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (frontend/'dist').rglob('*') if p.is_file()}
    assert frontend_assets
    for host in ('desarrollo.stepsapp.cl','cerroelplomo.stepsapp.cl'):
        for name,expected_sha in frontend_assets.items():
            with urlopen('https://'+host+'/web_tracker/'+name,timeout=20) as response:
                import hashlib
                assert hashlib.sha256(response.read()).hexdigest()==expected_sha
    with urlopen('http://127.0.0.1:8000/openapi.json',timeout=10) as response:paths=json.load(response)['paths']
    assert '/v1/receiver/poll' in paths and '/mobile/services' in paths
    print(json.dumps({'gps_commissioning':'healthy','commit':commit,'api_source_exact':True,'receiver_source_exact':True,'https_assets_exact':True,'cerro_receiver_online':True,'enabled_identities':expected,'existing_mobile_services_present':True,'teltonika_active':True,'credentials_private':True}))


if __name__=='__main__':main()
