"""Render original closed SyS payslips with a private loopback asset server."""

import argparse
import json
import os
from pathlib import Path
import subprocess


DATABASE = 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I'
PRIVATE = (Path('/opt/steps-validation'), Path('/srv/odoo-data/steps-anchor-validation'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'source-tools', 'data-dir', 'capsule', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--addons-path', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    paths = [args.runtime, args.source_tools, args.data_dir, args.capsule, *map(Path, args.addons_path.split(','))]
    if not any(output.is_relative_to(root) for root in PRIVATE) or output.exists():
        raise ValueError('Use a new private validation output directory')
    if not all(any(path.resolve(strict=True).is_relative_to(root) for root in PRIVATE) for path in paths):
        raise ValueError('Use the exact private Community runtime, addon paths, data and native capsule')
    source = Path(__file__).resolve().parent
    loader = source / 'original_report_loopback.py'
    if not loader.is_file() or not (source / 'probe_sys_stored_payslip_report.py').is_file():
        raise ValueError('Place the reviewed loopback runner and report probe beside this driver')
    output.mkdir(mode=0o750)
    subprocess.run(['chgrp', 'odoo', str(output)], check=True)
    pdfs = output / 'pdfs'
    subprocess.run(['install', '-d', '-m', '700', '-o', 'odoo', '-g', 'odoo', str(pdfs)], check=True)
    options = ['-c','/etc/odoo18-sys.conf','-d',DATABASE,'--db-filter=^'+DATABASE+'$',
               '--db_host=/var/run/postgresql','--addons-path='+args.addons_path,'--data-dir='+str(args.data_dir),
               '--load=base,web','--workers=0','--max-cron-threads=0','--without-demo=all','--no-http','--stop-after-init']
    command = ['unshare', '-n', 'bash', '-c', 'set -e; ip link set lo up; exec "$@"', 'bash',
               '/usr/bin/python3.10', str(loader), 'runuser', '-u', 'odoo', '--', '/usr/bin/python3.10',
               str(args.runtime / 'odoo-bin'), 'shell', *options]
    script = ('import json,sys\n'
              f'sys.path[:0]=[{str(source)!r},{str(args.source_tools.resolve())!r}]\n'
              'from probe_sys_stored_payslip_report import run\n'
              f'with open({str(args.capsule.resolve())!r}) as stream: reference=json.load(stream)\n'
              f'print("SYS_REPORT_PROOF="+json.dumps(run(env,reference,{str(pdfs)!r},1431)))\n')
    log = output / 'render.log'
    with os.fdopen(os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as fp:
        result = subprocess.run(command, input=script.encode(), stdout=fp, stderr=subprocess.STDOUT)
    records = [json.loads(line.split('=', 1)[1]) for line in log.read_text().splitlines() if line.startswith('SYS_REPORT_PROOF=')]
    if result.returncode or len(records) != 1:
        raise RuntimeError('The isolated Odoo report run did not produce a complete receipt')
    proof, = records
    receipt = {'code': result.returncode, 'business_intact': proof['historical_tables_preserved'], 'proof': proof}
    with os.fdopen(os.open(output/'receipt.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as fp:
        json.dump(receipt, fp)
    print(f"Rendered {len(proof['slips'])} original reports with retained action {proof['action']}")


if __name__ == '__main__':
    main()
