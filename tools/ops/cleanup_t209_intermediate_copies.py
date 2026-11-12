"""Remove only superseded T209 private copies; retain final tests and all backups."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import subprocess

PAIRS = [(environment, suffix) for environment in ('development', 'cerro') for suffix in ('a', 'b', 'c')] + [('qa-cerro', 'a')]
ROOT = Path('/opt/steps-validation')


def sql(statement):
    return subprocess.check_output(['sudo','-u','postgres','psql','-d','postgres','-At','-v','ON_ERROR_STOP=1'],
                                   input=statement, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        with open('/run/lock/steps-environments.lock', 'a') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            cleanup(True)
    else:
        cleanup(False)


def cleanup(apply):
    if apply:
        proof = json.loads((ROOT/'t209-delivery-evidence.json').read_text())
        assert proof['parity'] and proof['qa_isolation'] and proof['tests'] >= 72
        assert proof['versions']['step_packing_interplant'] == '18.0.1.0.3'
    result = []
    for environment, suffix in PAIRS:
        database = 'MANAGEMENT_QA_' + environment.upper() + '_t209' + suffix
        stage = ROOT / ('management_' + environment + '_t209' + suffix)
        assert stage.resolve() == stage and stage.parent == ROOT and not stage.is_symlink()
        if not stage.exists():
            continue
        proof = json.loads((stage/'baseline.json').read_text())
        assert proof, 'Expected private validation evidence'
        assert sql("SELECT count(*) FROM pg_stat_activity WHERE datname='%s'" % database) == '0', 'Private copy still in use'
        exists = sql("SELECT count(*) FROM pg_database WHERE datname='%s'" % database) == '1'
        size = int(sql("SELECT pg_database_size('%s')" % database)) if exists else 0
        files = [stage/'source.dump', stage/'data']
        for target in files:
            assert target.parent == stage and target.resolve() == target and not target.is_symlink()
        row = {'database':database, 'database_bytes':size, 'applied':apply}
        if apply:
            if exists:
                subprocess.run(['sudo','-u','postgres','dropdb','--',database],check=True)
            for target in files:
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
            (stage/'intermediate_copy_removed.json').write_text(json.dumps(row,indent=2))
        result.append(row)
    print(json.dumps({'tickets':[209],'intermediate_copies':result,'final_d_copies_and_deployment_backups':'retained'},indent=2))


if __name__ == '__main__':
    main()
