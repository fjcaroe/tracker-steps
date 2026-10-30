"""Serve report assets from the same private clone during PDF verification."""
from contextlib import contextmanager
import os
import pwd
import signal
import socket
import subprocess
import time
import urllib.request


@contextmanager
def report_assets_http(base, options, database, source, opts, stage, query):
    assert database.startswith('MANAGEMENT_QA_')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    url = 'http://127.0.0.1:' + str(port)
    query(database, "INSERT INTO ir_config_parameter(key,value) VALUES ('report.url','%s'),('web.base.url','%s') ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value" % (url,url))
    command = base + [v for v in options if v != '--no-http' and not v.startswith('--http-port=')]
    command += ['-d', database, '--db-filter=^'+database+'$', '--http-port='+str(port),
        '--http-interface=127.0.0.1', '--addons-path='+str(source)+','+opts['addons_path'], '--data-dir='+str(stage/'data'),
        '--logfile='+str(stage/'report-assets-http.log')]
    # Customer QA retains its deny-all egress policy. Its PDF renderer needs
    # this exact private clone HTTP endpoint for local CSS/fonts only. Caller
    # holds the shared environment lease; remove the narrow exception even on
    # failure, without permitting another host or database.
    rule = None
    process = None
    try:
        if database.startswith('MANAGEMENT_QA_QA-CERRO_'):
            assert os.geteuid() == 0 and opts['db_user'] == 'cerroqa_odoo18'
            uid = str(pwd.getpwnam('cerroqa_odoo18').pw_uid)
            rule = ['OUTPUT','-m','owner','--uid-owner',uid,'-d','127.0.0.1/32',
                    '-p','tcp','--dport',str(port),'-m','comment','--comment',
                    'STEPS_PRIVATE_REPORT_'+database,'-j','ACCEPT']
            assert subprocess.run(['/usr/sbin/iptables','-w','-C',*rule],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode != 0
            subprocess.run(['/usr/sbin/iptables','-w','-I','OUTPUT','1',*rule[1:]],check=True)
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for attempt in range(60):
            assert process.poll() is None, 'Private report asset server stopped'
            try:
                with urllib.request.urlopen(url+'/web/login?db='+database, timeout=5) as response:
                    if response.status == 200: break
            except OSError: time.sleep(1)
        else: raise AssertionError('Private report asset server did not start')
        yield
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
        if rule is not None:
            subprocess.run(['/usr/sbin/iptables','-w','-D',*rule],check=True)
            assert subprocess.run(['/usr/sbin/iptables','-w','-C',*rule],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode != 0
            print('CUSTOMER_QA_REPORT_LOOPBACK_REMOVED '+database,flush=True)
