"""Collect read-only live source, public asset, auth and rehearsal evidence for I9."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import urllib.request
import urllib.error


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('commit');p.add_argument('artifacts',type=Path)
    p.add_argument('--ui-reviewed',action='store_true',required=True)
    a=p.parse_args();assert re.fullmatch('[0-9a-f]{40}',a.commit)
    root=Path(__file__).resolve().parents[2]
    assert not a.artifacts.resolve().is_relative_to(root)
    log=(a.artifacts/('deploy-'+a.commit[:8]+'.log')).read_text()
    for marker in ('POSTGRES_PASSENGER_MIGRATION_OK idempotent=True existing_rows_preserved=True',
                   'POSTGRES_PASSENGER_SERVICE_FLOW_OK three_passengers=True driver_isolation=True',
                   'POSTGRES_PASSENGER_FIXTURES_ROLLED_BACK','POSTGRES_SCHEMA_REHEARSAL_OK',
                   'MOBILE_SOURCE_CONCURRENCY_OK','VERIFIED_ALL_MOBILE_JS_CSS','DEPLOYED_RELEASE='+a.commit):
        assert marker in log,marker
    assert re.search(r'Tests\s+165 passed',log)
    assert re.search(r'68 passed', (a.artifacts/'backend-test.log').read_text())
    screenshot=a.artifacts/'my-service-375.bottom.png'
    assert int.from_bytes(screenshot.read_bytes()[16:20],'big')==375
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',a.commit,'backend/tracker_py/app'],cwd=root,text=True).splitlines()
    expected={}
    for path in paths:
        if path.endswith('.py'):
            data=subprocess.check_output(['git','show',a.commit+':'+path],cwd=root).replace(b'\r\n',b'\n')
            expected[path.removeprefix('backend/tracker_py/')]=hashlib.sha256(data).hexdigest()
    code="from pathlib import Path; import hashlib,json; root=Path('/opt/fernando_odoo18/apis/backend/tracker_py'); print(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() for p in (root/'app').rglob('*.py') if '__pycache__' not in p.parts}))"
    actual=json.loads(subprocess.check_output(['ssh','odoo-new','python3 -c '+shlex.quote(code)],text=True))
    assert actual==expected,'Effective API source differs from the certified commit'
    query="SELECT (SELECT count(*) FROM users WHERE username LIKE 'private-i9-%')+(SELECT count(*) FROM cost_centers WHERE name='Private I9 test')+(SELECT count(*) FROM machines WHERE name='Private I9 vehicle')+(SELECT count(*) FROM mobile_passenger_services WHERE name='Private I9 service')"
    result=subprocess.check_output(['ssh','odoo-new','sudo -u postgres psql -At -d tracker_steps -c '+shlex.quote(query)],text=True)
    assert result.strip()=='0','Test fixtures found in production; do not delete automatically'
    api='https://stepsapp.cl/tracker-steps'
    assert json.load(urllib.request.urlopen(api+'/health',timeout=30))['status']=='ok'
    try:
        urllib.request.urlopen(api+'/mobile/services',timeout=30)
    except urllib.error.HTTPError as exc:
        assert exc.code==401
    else:
        raise AssertionError('Anonymous manifest access must be denied')
    asset,sha=re.search(r'VERIFIED_JS=(\S+) SHA256=([0-9a-f]{64})',log).groups()
    main=urllib.request.urlopen('https://stepsapp.cl/truck/'+asset,timeout=30).read()
    assert hashlib.sha256(main).hexdigest()==sha and '1.3.0' in main.decode()
    chunk=re.search(r'dist/(assets/TrackerModule-[\w-]+\.js)',log).group(1)
    source=urllib.request.urlopen('https://stepsapp.cl/truck/'+chunk,timeout=30).read().decode()
    assert 'Mi servicio' in source
    proof={'ticket':46,'iteration':'I9','commit':a.commit,'tracker_version':'1.3.0','backend_tests':68,'app_tests':165,
           'postgres_rehearsal':True,'effective_source_matches':True,'live_auth_required':True,'live_fake_records':0,
           'ui375_reviewed':a.ui_reviewed,'screenshot_sha256':hashlib.sha256(screenshot.read_bytes()).hexdigest(),
           'asset':asset,'asset_sha256':sha,'tracker_chunk':chunk,
           'backup':re.search(r'BACKUP=(\S+)',log).group(1),'reviewed_message':9174}
    (a.artifacts/'delivery.json').write_text(json.dumps(proof,indent=2))
    print('MOBILE_I9_DELIVERY_COLLECTED tests=68+165 postgres=True live_source=True auth=True')


if __name__=='__main__':main()
