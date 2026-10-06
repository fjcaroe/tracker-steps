"""Stop an old private QA server and disable Admin's cross-database scheduler.

Preserves every database, source directory and schedule definition. Recovery
configurations and original launch arguments stay in a private server backup.
"""
import configparser
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from canonical_ports import setting, run

assert os.geteuid() == 0
registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
target = registry['environments']['admin']
assert target['role'] == 'legacy' and target['database'] is None
conf = Path(target['config'])
cfg = configparser.ConfigParser(interpolation=None)
cfg.read(conf)
assert cfg['options'].get('db_name') in (None, '', 'False')


def arguments(argv):
    result = {}
    for index, arg in enumerate(argv):
        key, sep, value = arg.partition('=')
        if key in ('-c', '-d', '--http-port', '--http-interface', '--max-cron-threads', '--workers'):
            result[key] = value if sep else argv[index + 1]
    return result


with open('/run/lock/steps-environments.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    obsolete = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            raw = path.read_bytes()
            argv = raw.decode(errors='replace').split('\0')
        except OSError:
            continue
        if not Path(argv[0]).name.startswith('python') or not any(Path(a).name == 'odoo-bin' for a in argv):
            continue
        assert not any(a in ('-u', '-i', '--update', '--init') or a.startswith(('--update=', '--init=')) for a in argv), 'Concurrent upgrade'
        opts = arguments(argv)
        if opts.get('-d') == 'T_SYS_REFRESH_20260929':
            assert opts == {'-c': '/etc/odoo18-demo-sys.conf', '-d': 'T_SYS_REFRESH_20260929',
                            '--http-port': '18091', '--http-interface': '127.0.0.1',
                            '--max-cron-threads': '0', '--workers': '0'}, 'Unexpected QA process scope'
            obsolete.append((path, raw))
    backup = Path('/opt/steps_backups') / ('runtime_scope_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    original = conf.read_bytes()
    shutil.copy2(conf, backup/'admin.conf')
    (backup/'service-definition.txt').write_text(subprocess.check_output(['systemctl', 'cat', target['service']], text=True))
    changed = setting(original.decode(), 'max_cron_threads', '0')
    assert conf.read_bytes() == original, 'Concurrent config change'
    if changed.encode() != original:
        conf.write_text(changed)
        try:
            run('systemctl', 'restart', target['service'])
            run('systemctl', 'is-active', '--quiet', target['service'])
        except Exception:
            conf.write_bytes(original)
            run('systemctl', 'restart', target['service'])
            raise
    stopped = []
    for path, raw in obsolete:
        pid = int(path.parent.name)
        saved = backup/('launch-'+str(pid)+'.bin')
        saved.write_bytes(raw)
        saved.chmod(0o600)
        assert path.read_bytes() == raw, 'QA PID changed'
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not path.exists():
                break
            time.sleep(1)
        assert not path.exists(), 'QA process did not stop gracefully'
        stopped.append(pid)
    result = {'backup': str(backup), 'admin_cron_threads': 0, 'stopped_private_qa': stopped,
              'databases_preserved': True}
    (backup/'verified.json').write_text(json.dumps(result))
    print('RUNTIME_SCOPE_OK ' + json.dumps(result))
