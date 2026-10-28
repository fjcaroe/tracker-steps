"""Create owned tablespaces for new private rehearsals; never move existing DBs.

Keep PostgreSQL/WAL reserve checks. Do not change roles, passwords, server
configuration, existing databases or existing tablespaces.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def query(statement):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-XAt',
                                    '-v', 'ON_ERROR_STOP=1', '-d', 'postgres', '-c', statement], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    root = args.root.resolve()
    assert root.parent == Path('/opt/steps-validation')
    assert root.name == 'community-payroll-storage-20261028' and not args.root.is_symlink()
    who = pwd.getpwnam('postgres')
    report = {'existing_databases_moved': False, 'server_configuration_changed': False,
              'credentials_changed': False, 'tablespaces': {},
              'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        root.mkdir(mode=0o755, exist_ok=True)
        assert os.stat(root).st_uid == 0
        for mode, config in [('community', '/etc/dev_odoo18.conf'),
                             ('cerro', '/etc/odoo18-cerroelplomo.conf')]:
            cfg = configparser.ConfigParser(interpolation=None)
            assert cfg.read(config)
            role = cfg['options']['db_user']
            name = 'steps_community_storage_20261028_' + mode
            path = root / mode
            assert not path.is_symlink() and path.resolve().is_relative_to(root)
            path.mkdir(mode=0o700, exist_ok=True)
            os.chown(path, who.pw_uid, who.pw_gid)
            existing = query("SELECT jsonb_build_object('location',pg_tablespace_location(oid),'owner',pg_get_userbyid(spcowner)) FROM pg_tablespace WHERE spcname='" + name + "'")
            if existing:
                assert json.loads(existing) == {'location': str(path), 'owner': role}
            else:
                assert not list(path.iterdir()), 'New tablespace directory must be empty'
                query('CREATE TABLESPACE ' + quote(name) + ' OWNER ' + quote(role) + " LOCATION '" + str(path) + "'")
            proof = json.loads(query("SELECT jsonb_build_object('location',pg_tablespace_location(oid),'owner',pg_get_userbyid(spcowner)) FROM pg_tablespace WHERE spcname='" + name + "'"))
            assert proof == {'location': str(path), 'owner': role}
            report['tablespaces'][mode] = dict(proof, name=name)
        stat = os.statvfs(root)
        report['available_bytes'] = stat.f_bavail * stat.f_frsize
        assert report['available_bytes'] >= 2 * 1024 ** 3
        (root / 'storage-proof.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'tablespaces': [row['name'] for row in report['tablespaces'].values()],
                      'available_bytes': report['available_bytes'], 'existing_databases_moved': False}))


if __name__ == '__main__':
    main()
