"""Exact Git package, fresh destination-copy rehearsal and scoped Tracker publication.

Run on odoo-new as root with SUDO_USER. Never writes Odoo data or credentials.
API baseline is the mobile release already installed when this upgrade was reviewed.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import time
from urllib.request import urlopen

API=Path('/opt/fernando_odoo18/apis/backend/tracker_py')
BASE=Path('/opt/steps-validation/gps-commissioning-20261031')
BASELINE='0254eb9d0f212e33ee5dd67930e5dfa8f73ddb00'
MIGRATION='backend/tracker_py/migrations/20261031_receiver_commissioning.up.sql'


def run(*args,**kw):return subprocess.run([str(a) for a in args],check=True,**kw)


def query(db,sql):
    return subprocess.check_output(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-At','-d',db],input=sql,text=True).strip()


def sha(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def tree(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*.py')) if '__pycache__' not in p.parts}


def baseline(source):
    names=subprocess.check_output(['git','-C',str(source),'ls-tree','-r','--name-only',BASELINE,'backend/tracker_py/app'],text=True).splitlines()
    return {name.removeprefix('backend/tracker_py/app/'):hashlib.sha256(subprocess.check_output(['git','-C',str(source),'show',BASELINE+':'+name]).replace(b'\r\n',b'\n')).hexdigest() for name in names if name.endswith('.py')}


def columns(db):
    return json.loads(query(db,"SELECT json_object_agg(t,cols) FROM (SELECT table_name t, string_agg(quote_ident(column_name),',' ORDER BY ordinal_position) cols FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) s"))


def snapshot(db,cols):
    return {table:query(db,'SELECT count(*)::text||\':\'||md5(COALESCE(string_agg(h,\'\' ORDER BY h),\'\')) FROM (SELECT md5(row_to_json(x)::text) h FROM (SELECT '+fields+' FROM public."'+table+'") x) hashes') for table,fields in cols.items()}


def wait_api():
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8000/openapi.json',timeout=3) as response:paths=json.load(response)['paths']
            assert '/v1/receiver/poll' in paths and '/mobile/services' in paths
            return
        except (OSError,AssertionError):time.sleep(1)
    raise RuntimeError('API did not start with commissioning and existing mobile endpoints')


def configure_frontend(source,commit,scope,backup):
    target=Path('/var/www/steps-tracker-releases')/commit
    if not target.exists():shutil.copytree(source/'dist',target)
    site=Path('/etc/nginx/sites-enabled/stepsapp' if scope=='dev' else '/etc/nginx/sites-enabled/cerroelplomo.stepsapp.cl').resolve()
    marker='include /etc/nginx/snippets/steps-tracker-portal.conf;'
    new_marker='include /etc/nginx/snippets/steps-tracker-'+scope+'-gps.conf;'
    original=site.read_text();assert original.count(marker)+original.count(new_marker)==1,'Unexpected nginx portal layout'
    if scope=='dev':assert 'server_name desarrollo.stepsapp.cl;' in original
    shutil.copy2(site,backup/('nginx-'+scope+'.conf'))
    snippet=Path('/etc/nginx/snippets/steps-tracker-'+scope+'-gps.conf')
    common=Path('/etc/nginx/snippets/steps-tracker-portal.conf').read_text()
    previous=snippet.read_text() if snippet.exists() else None
    if previous is not None:
        roots=set(re.findall(r'/var/www/steps-tracker-releases/[a-f0-9]{40}',previous))
        assert len(roots)==1,'Unexpected frontend release roots'
        # Only own the Web Tracker locations. Keep mobile releases and the
        # dedicated Development API exactly as installed in the private overlay.
        assert previous.split('location = /truck')[0]==common.replace('/var/www/web_tracker_portal',next(iter(roots))).split('location = /truck')[0],'Unreviewed Web Tracker location drift'
        (backup/('snippet-'+scope+'.conf')).write_text(previous)
    updated=previous.replace(next(iter(roots)),str(target)) if previous is not None else common.replace('/var/www/web_tracker_portal',str(target))
    entries=prepare_tracker_entries(updated,target)
    updated=tracker_entry_locations(updated,target,scope,entries)
    snippet.write_text(updated)
    site.write_text(original.replace(marker,new_marker))
    host='desarrollo.stepsapp.cl' if scope=='dev' else 'cerroelplomo.stepsapp.cl'
    try:
        run('nginx','-t');run('systemctl','reload','nginx')
        # A graceful reload can briefly serve a request through an older worker.
        for _ in range(20):
            try:
                with urlopen('https://'+host+'/web_tracker/',timeout=20) as response:matched=response.read()==(source/'dist/index.html').read_bytes()
                with urlopen('https://'+host+'/tracker',timeout=20) as response:matched=matched and response.read()==(entries/'gps.html').read_bytes()
                with urlopen('https://'+host+'/tracker/jornada/',timeout=20) as response:matched=matched and response.read()==(entries/'jornada.html').read_bytes()
            except OSError:matched=False
            if matched:break
            time.sleep(.5)
        assert matched,'Served Tracker entries do not match the tested package'
        with urlopen('https://'+host+'/truck/?compat=1',timeout=20) as response:
            assert response.geturl().endswith('/tracker/jornada/?compat=1')
            assert response.read()==(entries/'jornada.html').read_bytes()
        mobile = installed_mobile_root(updated)
        for p in (mobile/'assets').iterdir():
            with urlopen('https://'+host+'/tracker/jornada/assets/'+p.name,timeout=20) as response:
                assert response.read()==p.read_bytes(), 'Unexpected Jornada asset'
        for p in (source/'dist/assets').iterdir():
            with urlopen('https://'+host+'/web_tracker/assets/'+p.name,timeout=20) as response:assert hashlib.sha256(response.read()).hexdigest()==hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        site.write_text(original)
        if previous is None:snippet.unlink()
        else:snippet.write_text(previous)
        run('nginx','-t');run('systemctl','reload','nginx');raise
    print('GPS_FRONTEND_VERIFIED scope='+scope,flush=True)


def jornada_session_gate(html):
    entry = re.compile(r'<script\b[^>]*\bsrc="(\./assets/[\w.-]+\.js)"[^>]*></script>')
    matches = entry.findall(html)
    assert len(matches) == 1, 'Unexpected Steps Móvil entry script'
    script = """<script type="module">
const panel = document.getElementById('steps-jornada-access');
const accessMessage = document.getElementById('steps-jornada-message');
try {
  const response = await fetch('/steps_tracker/context', {
    credentials: 'same-origin', redirect: 'manual', cache: 'no-store',
    headers: { Accept: 'application/json' },
  });
  if (response.type === 'opaqueredirect' || [302, 303, 401].includes(response.status)) {
    const login = new URL('/tracker', location.origin);
    login.search = location.search;
    login.searchParams.set('entrada', 'jornada');
    login.hash = location.hash;
    location.replace(login.href);
  } else if (response.status === 403) {
    accessMessage.textContent = 'Tu cuenta no tiene acceso a Jornada y terreno.';
  } else {
    if (!response.ok) throw new Error();
    const context = await response.json();
    if (context.vehicle_limited || context.role === 'viewer') {
      accessMessage.textContent = 'Tu cuenta tiene acceso a GPS y recorridos. Jornada y terreno requiere un permiso adicional.';
    } else {
      await import(ENTRY);
      panel.remove();
    }
  }
} catch {
  accessMessage.textContent = 'Jornada no está disponible en este momento. Recarga la página para volver a intentar.';
}
</script>""".replace('ENTRY', json.dumps(matches[0]))
    panel = ('<section id="steps-jornada-access" style="margin:2rem auto;padding:1rem;max-width:36rem">'
             '<h1>Jornada y terreno</h1><p id="steps-jornada-message" role="status">Comprobando tu sesión…</p>'
             '<a href="/tracker">Ir a GPS y recorridos</a></section>')
    assert html.count('</body>') == 1
    return entry.sub('', html).replace('<body>', '<body>'+panel, 1).replace('</body>', script+'</body>', 1)


def tracker_shell(html, section):
    """Keep the two tested applications and add a shared, same-origin switch."""
    assert html.count('<body>') == 1
    if section == 'jornada':
        html = jornada_session_gate(html)
    links = [('gps', '/tracker', 'GPS y recorridos'), ('jornada', '/tracker/jornada/', 'Jornada y terreno')]
    navigation = ''.join(
        f'<a href="{url}"' + (' aria-current="page"' if key == section else '') + f'>{label}</a>'
        for key, url, label in links
    )
    style = """<style>
    .steps-tracker-switch {display:flex;flex-wrap:wrap;gap:.35rem;justify-content:center;padding:.45rem;
      background:#123c33;color:#fff;font:600 .875rem system-ui,sans-serif}
    .steps-tracker-switch a {color:inherit;text-decoration:none;padding:.45rem .75rem;border-radius:.5rem}
    .steps-tracker-switch a[aria-current] {background:#e6efd9;color:#123c33}
    .steps-tracker-switch a:focus-visible {outline:2px solid currentColor;outline-offset:2px}
    </style>"""
    return html.replace('</head>',style+'</head>',1).replace(
        '<body>', '<body><nav class="steps-tracker-switch" aria-label="Secciones de Steps Tracker">'+navigation+'</nav>',1
    ).replace('<title>Steps Móvil</title>','<title>Steps Tracker · Jornada</title>')


def installed_mobile_root(content):
    mobile = re.findall(r'alias (/var/www/steps-mobile-releases/[a-f0-9]{40})/assets/;',content)
    assert len(mobile) == 1, 'Review the installed Steps Móvil release before publishing'
    return Path(mobile[0])


def prepare_tracker_entries(content,target):
    mobile = installed_mobile_root(content)
    entries = Path('/var/www/steps-tracker-entry-releases')/(target.name+'-'+mobile.name)
    entries.mkdir(parents=True,exist_ok=True)
    for name, original in [('gps', target/'index.html'), ('jornada', mobile/'index.html')]:
        page = entries/(name+'.html')
        rendered = tracker_shell(original.read_text(encoding='utf-8'),name)
        if page.exists():
            assert page.read_text(encoding='utf-8') == rendered, 'Unexpected entry shell drift'
        else:
            page.write_text(rendered,encoding='utf-8')
    return entries


def tracker_entry_locations(content,target,scope,entries=None):
    """Public login shell; business data remains behind the existing Odoo BFF."""
    start='# BEGIN STEPS TRACKER ENTRY\n';end='# END STEPS TRACKER ENTRY\n'
    if start in content:
        assert content.count(start)==content.count(end)==1
        content=re.sub(re.escape(start)+r'.*?'+re.escape(end),'',content,flags=re.S)
    else:assert not re.search(r'location\s+(?:(?:=|\^~|~\*?)\s+)?/tracker(?:[/\s{])',content),'Unknown Tracker route requires review'
    if entries is not None:
        legacy = 'location = /truck { return 302 /tracker/jornada/$is_args$args; }'
        content, count = re.subn(r'location = /truck \{ return (?:301 /truck/|302 /tracker(?:/jornada/)?\$is_args\$args); \}',lambda _:legacy,content)
        assert count == 1, 'Unexpected legacy entry'
        legacy_slash = legacy.replace('location = /truck ', 'location = /truck/ ')
        content = re.sub(r'location = /truck/ \{ return 302 /tracker(?:/jornada/)?\$is_args\$args; \}\n?', '',content)
        content = content.rstrip()+'\n\n'+legacy_slash+'\n'
    elif scope=='cerro':
        content=content.replace('location = /truck { return 301 /truck/; }','location = /truck { return 302 /tracker$is_args$args; }')
        if 'location = /truck/ {' not in content:content+='\nlocation = /truck/ { return 302 /tracker$is_args$args; }\n'
    gps = entries/'gps.html' if entries is not None else target/'index.html'
    jornada = '' if entries is None else '''
location = /tracker/jornada { return 302 /tracker/jornada/$is_args$args; }
location = /tracker/jornada/ { rewrite ^ /tracker/jornada/index.html last; }
location = /tracker/jornada/index.html {
    internal;
    alias '''+str(entries/'jornada.html')+''';
    default_type text/html;
    add_header Cache-Control "no-store" always;
}
location ^~ /tracker/jornada/assets/ { rewrite ^/tracker/jornada/(assets/.+)$ /truck/$1 last; }
location ~ ^/tracker/jornada/(manifest[.]webmanifest|icon[.]svg|sw[.]js)$ {
    rewrite ^/tracker/jornada/(.+)$ /truck/$1 last;
}
'''
    return content+start+'''location = /tracker {
    alias '''+str(gps)+''';
    default_type text/html;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;
}
location = /tracker/ { return 302 /tracker$is_args$args; }
'''+jornada+end


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['qa','development','production']);parser.add_argument('source',type=Path);a=parser.parse_args()
    assert os.geteuid()==0
    source=a.source.resolve();commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
    expected=tree(source/'backend/tracker_py/app');old=baseline(source)
    BASE.mkdir(parents=True,exist_ok=True);stage=BASE/commit;stage.mkdir(exist_ok=True);stage.chmod(0o755)
    private=stage/'private';private.mkdir(exist_ok=True,mode=0o700);private.chmod(0o700)
    dist_hash={str(p.relative_to(source/'dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'dist').rglob('*') if p.is_file()}
    assert dist_hash and (source/'dist/index.html').exists()
    proof_file=stage/'qa.json';production_cols=columns('tracker_steps')
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('GPS_WAIT_SHARED_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        assert query('CERRO_EL_PLOMO',"SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")=='0'
        if a.action=='qa':
            assert not proof_file.exists(),'A successful QA proof is immutable'
            assert tree(API/'app')==old,'Unreviewed API drift / downgrade risk'
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');db='COBAN_QA_'+stamp
            dump=private/'tracker_steps.dump'
            with dump.open('wb') as output:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=output)
            run('pg_restore','--file=/dev/null',dump)
            run('sudo','-u','postgres','createdb',db)
            try:
                with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
                before=snapshot(db,production_cols)
                for _ in range(2):run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',db,'-f',source/MIGRATION,stdout=subprocess.DEVNULL)
                assert snapshot(db,production_cols)==before,'Existing records changed during migration'
                with (private/'receiver-unit.log').open('w') as log:run('/usr/bin/python3.10','-m','unittest','receivers.coban.test_receiver','-v',cwd=source,stdout=log,stderr=subprocess.STDOUT)
                assert '\nOK' in (private/'receiver-unit.log').read_text()
                with (private/'flow.log').open('w') as log:
                    run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=test-only-rehearsal','PYTHONPATH='+str(source)+':'+str(source/'backend/tracker_py'),str(API/'.venv/bin/python'),'-m','receivers.coban.rehearse',cwd=source,stdout=log,stderr=subprocess.STDOUT)
                assert 'COBAN_COPY_QA_OK' in (private/'flow.log').read_text()
                assert tree(API/'app')==old
                proof_file.write_text(json.dumps({'commit':commit,'api_baseline':old,'api_package':expected,'dist':dist_hash,'fresh_target_copy':True,'all_existing_records_preserved':True,'full_tcp_flow':True,'migration_idempotent':True,'qa_database':db},indent=2))
                print('GPS_TARGET_COPY_QA_OK',flush=True)
            finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
            return
        proof=json.loads(proof_file.read_text());assert proof['commit']==commit and proof['api_package']==expected and proof['dist']==dist_hash
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=private/('backup-'+a.action+'-'+stamp);backup.mkdir(mode=0o700)
        # The shared legacy portal and mobile frontend are read-only throughout.
        untouched={str(path):{str(p.relative_to(path)):sha(p) for p in path.rglob('*') if p.is_file()} for path in (Path('/var/www/web_tracker_portal'),Path('/var/www/steps-truck-frontend'))}
        if a.action=='development':
            assert tree(API/'app')==old
            configure_frontend(source,commit,'dev',backup)
            (stage/'development.json').write_text(json.dumps({'commit':commit,'dist':dist_hash,'backup':str(backup)}))
            print('GPS_DEVELOPMENT_REVIEW_READY',flush=True);return
        assert json.loads((stage/'development.json').read_text())['dist']==dist_hash
        assert tree(API/'app')==old,'API changed since target-copy QA'
        with (backup/'tracker_steps.dump').open('wb') as output:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=output)
        run('pg_restore','--file=/dev/null',backup/'tracker_steps.dump')
        shutil.copytree(API/'app',backup/'api-app',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree('/etc/steps-coban',backup/'receiver-config')
        cfg_path=Path('/etc/steps-coban/config.json');cfg=json.loads(cfg_path.read_text());old_receiver=Path('/opt/steps-coban/current').resolve()
        (backup/'receiver-release.txt').write_text(str(old_receiver))
        receiver_identity=pwd.getpwnam('steps-coban');api_identity=pwd.getpwnam(os.environ['SUDO_USER'])
        before=snapshot('tracker_steps',production_cols)
        run('systemctl','stop','steps-coban.service','tracker-steps-api.service')
        shutil.copytree('/var/lib/steps-coban',backup/'receiver-data')
        try:
            run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d','tracker_steps','-f',source/MIGRATION,stdout=subprocess.DEVNULL)
            assert snapshot('tracker_steps',production_cols)==before
            for p in (source/'backend/tracker_py/app').rglob('*.py'):
                target=API/'app'/p.relative_to(source/'backend/tracker_py/app');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);os.chown(target,api_identity.pw_uid,api_identity.pw_gid)
            assert tree(API/'app')==expected
            run('systemctl','start','tracker-steps-api.service');wait_api()
            release=Path('/opt/steps-coban/releases')/commit;release.mkdir(parents=True);shutil.copytree(source/'receivers',release/'receivers',ignore=shutil.ignore_patterns('__pycache__'))
            cache=Path('/var/lib/steps-coban/devices.json');assert not cache.exists()
            cache.write_bytes(Path(cfg['mapping']).read_bytes());cache.chmod(0o600);os.chown(cache,receiver_identity.pw_uid,receiver_identity.pw_gid)
            cfg['mapping']=str(cache);cfg['companies']=json.loads(query('tracker_steps',"SELECT json_agg(company_id ORDER BY company_id) FROM gps_tenants WHERE issuer='CERRO_EL_PLOMO'"));assert cfg['companies']
            cfg_path.write_text(json.dumps(cfg,indent=2));cfg_path.chmod(0o640);os.chown(cfg_path,0,receiver_identity.pw_gid)
            link=Path('/opt/steps-coban/current');link.unlink();link.symlink_to(release,target_is_directory=True)
            run('systemctl','start','steps-coban.service')
            for _ in range(20):
                online=query('tracker_steps',"SELECT count(*)=count(receiver_seen_at) AND bool_and(receiver_seen_at>now()-interval '30 seconds') FROM gps_tenants WHERE issuer='CERRO_EL_PLOMO'")
                if online=='t':break
                time.sleep(1)
            assert online=='t','Receiver must poll every mapped Cerro company'
            configure_frontend(source,commit,'cerro',backup)
            for root,files in untouched.items():assert {str(p.relative_to(root)):sha(p) for p in Path(root).rglob('*') if p.is_file()}==files
            for service in ('steps-coban','tracker-steps-api','teltonika-ingest','odoo18-cerroelplomo'):run('systemctl','is-active','--quiet',service)
            (stage/'production.json').write_text(json.dumps({'commit':commit,'backup':str(backup),'api_exact':True,'existing_records_preserved':True,'receiver_heartbeat_all_companies':True,'legacy_and_mobile_frontends_untouched':True,'receiver_release':str(release),'dist':dist_hash},indent=2))
            print('GPS_PRODUCTION_DEPLOY_OK backup='+str(backup),flush=True)
        except Exception:
            run('systemctl','stop','steps-coban.service','tracker-steps-api.service')
            shutil.copytree(backup/'api-app',API/'app',dirs_exist_ok=True)
            # Remove only package-added Python files; never restore a database over new data.
            for name in set(expected)-set(old):(API/'app'/name).unlink(missing_ok=True)
            shutil.copytree(backup/'receiver-config','/etc/steps-coban',dirs_exist_ok=True)
            link=Path('/opt/steps-coban/current');link.unlink();link.symlink_to(old_receiver,target_is_directory=True)
            run('systemctl','start','tracker-steps-api.service','steps-coban.service')
            raise


if __name__=='__main__':main()
