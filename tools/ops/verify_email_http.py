"""Actual session authentication on a private clone with disposable, committed test users."""
import json
import os
import secrets
import signal
import socket
import subprocess
import time
import urllib.request


def verify_http(base, options, database, source, opts, stage):
    assert database.startswith('MANAGEMENT_QA_'), 'Never create authentication fixtures in a live database'
    login='qa.'+secrets.token_hex(8)+'@example.invalid'
    password=secrets.token_urlsafe(32)
    shell_options=options+['-d',database,'--db-filter=^'+database+'$',
        '--addons-path='+str(source)+','+opts['addons_path'],'--data-dir='+str(stage/'data'),'--log-level=error']
    def shell(code):
        result=subprocess.run(base[:4]+[base[4],'shell']+shell_options,input=code,text=True,capture_output=True,check=True)
        return result.stdout
    fixture="""import json
u=env['res.users'].with_context(no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True).create({
'name':'QA email HTTP','login':LOGIN,'password':PASSWORD,'groups_id':[(6,0,env.ref('base.group_user').ids)]})
pid=u.partner_id.id
env.cr.commit()
print('HTTP_FIXTURE '+json.dumps({'user_id':u.id,'partner_id':pid}))
"""
    output=shell('LOGIN='+repr(login)+'\nPASSWORD='+repr(password)+'\n'+fixture)
    ids=json.loads(next(line.split(' ',1)[1] for line in output.splitlines() if line.startswith('HTTP_FIXTURE ')))
    process=None
    try:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        command=base+[v for v in options if v!='--no-http' and not v.startswith('--http-port=')]
        command+=['-d',database,'--db-filter=^'+database+'$','--http-port='+str(port),
            '--addons-path='+str(source)+','+opts['addons_path'],'--data-dir='+str(stage/'data'),
            '--logfile='+str(stage/'email-http.log')]
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        url='http://127.0.0.1:'+str(port)
        for attempt in range(60):
            assert process.poll() is None, 'Private HTTP process stopped'
            try:
                with urllib.request.urlopen(url+'/web/login?db='+database,timeout=5) as response:
                    assert response.status==200 and b'name="password"' in response.read()
                break
            except (OSError,AssertionError):time.sleep(1)
        else:raise AssertionError('Private login form did not start')
        def authenticate(value,secret):
            body=json.dumps({'jsonrpc':'2.0','method':'call','params':{'db':database,'login':value,'password':secret}}).encode()
            request=urllib.request.Request(url+'/web/session/authenticate',data=body,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
        for value in (login.lower(),login.upper(),'Qa.'+login[3:]):
            assert authenticate(value,password).get('result',{}).get('uid')==ids['user_id'], 'Expected same identity'
        assert 'error' in authenticate(login,password+'wrong'), 'Wrong password must remain rejected'
        shell("u=env['res.users'].browse(%s)\nu.active=False\nenv.cr.commit()\n"%ids['user_id'])
        assert 'error' in authenticate(login.upper(),password), 'Inactive account must remain rejected'
        print('EMAIL_LOGIN_HTTP_OK '+json.dumps({'database':database,'case_variants':3,
            'invalid_password_denied':True,'inactive_account_denied':True,'login_form':True}),flush=True)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10)
        cleanup="""u=env['res.users'].with_context(active_test=False).browse(USER_ID).exists()
assert u and u.login==LOGIN
p=u.partner_id
assert p.id==PARTNER_ID
env['res.users.log'].sudo().search([('create_uid','=',u.id)]).unlink()
env['res.device.log'].sudo().search([('user_id','=',u.id)]).unlink()
u.with_context(tracking_disable=True).unlink()
p.with_context(tracking_disable=True).unlink()
env.cr.commit()
print('HTTP_FIXTURE_REMOVED')
"""
        output=shell('USER_ID='+repr(ids['user_id'])+'\nPARTNER_ID='+repr(ids['partner_id'])+'\nLOGIN='+repr(login)+'\n'+cleanup)
        assert 'HTTP_FIXTURE_REMOVED' in output
