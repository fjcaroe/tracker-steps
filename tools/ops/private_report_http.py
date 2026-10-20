"""Serve report assets from the same private clone during PDF verification."""
from contextlib import contextmanager
import os
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
        '--addons-path='+str(source)+','+opts['addons_path'], '--data-dir='+str(stage/'data'),
        '--logfile='+str(stage/'report-assets-http.log')]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for attempt in range(60):
            assert process.poll() is None, 'Private report asset server stopped'
            try:
                with urllib.request.urlopen(url+'/web/login?db='+database, timeout=5) as response:
                    if response.status == 200: break
            except OSError: time.sleep(1)
        else: raise AssertionError('Private report asset server did not start')
        yield
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
