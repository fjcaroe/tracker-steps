"""Run a private Odoo shell and its report asset server in one network namespace."""
import os
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener


def run(command):
    shell = command.index('shell')
    options = [item for item in command[shell + 1:]
               if item not in ('--no-http', '--stop-after-init')
               and not item.startswith(('--logfile=', '--http-port=', '--http-interface='))]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    opener = build_opener(ProxyHandler({}))
    server = subprocess.Popen(command[:shell] + options + [
        '--http-interface=127.0.0.1', f'--http-port={port}', '--no-database-list'],
        stdin=subprocess.DEVNULL)
    try:
        for _ in range(90):
            if server.poll() is not None:
                raise RuntimeError('Private report asset server stopped')
            try:
                with opener.open(url + '/web/health', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError('Private report asset server did not start')
        # sudo preserves no user-provided environment. Pass only the local asset
        # URL after switching users, preserving the original Odoo command.
        command = command[:3] + ['env', f'STEPS_PRIVATE_REPORT_URL={url}'] + command[3:]
        return subprocess.run(command, env={**os.environ, 'NO_PROXY': '127.0.0.1'}, timeout=180).returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
