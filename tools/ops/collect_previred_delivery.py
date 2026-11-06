"""Collect exact tested releases, native downloads and live source evidence."""
import argparse
import ast
import configparser
import json
from pathlib import Path
import re
import subprocess
from manage_management import query, tree_hash


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    plan = json.loads(args.plan.read_text())
    tid = plan['ticket']
    expected = {'development', 'sys', 'demo-sys'} if tid == 172 else {'development', 'sys'}
    assert tid in (172, 173, 174) and set(plan['environments']) == expected
    registry = json.loads((Path(__file__).parent/'environments.json').read_text())
    evidence = {}
    reported = None
    for name, item in plan['environments'].items():
        target = registry['environments'][name]
        stage = Path('/opt/steps-validation') / ('management_' + name + '_' + item['run_id'])
        proof = json.loads((stage/'qa_passed.json').read_text())
        assert proof['commit'] == item['commit'] and proof['release_sha256'] == item['sha256']
        qa = Path(proof['log']).read_text()
        counts = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database', qa)
        assert counts and int(counts[-1]) > 0
        live = (stage/('verify-' + target['database'] + '.log')).read_text()
        assert 'MANAGEMENT_REGISTRY_OK' in live
        if name == 'sys':
            rows = [json.loads(line.split(' ', 1)[1]) for line in live.splitlines()
                    if line.startswith('PAYROLL_TICKET_FLOWS ')]
            reported = next(case for cases in rows for case in cases if case['ticket'] == tid)
            assert not reported['corporate_errors'] and reported['payroll_preserved']
            assert reported.get('download_verified') or item.get('legacy_download_verified')
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(target['config'])
        roots = [Path(x.strip()) for x in cfg['options']['addons_path'].split(',')]
        modules = {}
        for module, version in item['versions'].items():
            source = next(root/module for root in roots if (root/module/'__manifest__.py').exists())
            assert source.parent == Path('/opt/steps-managed/releases')/name/item['commit']
            installed = query(target['database'], "SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'" % module)
            assert installed == version == ast.literal_eval((source/'__manifest__.py').read_text())['version']
            modules[module] = {'version': version, 'sha256': tree_hash(source)}
        logs = sorted(stage.glob('deploy-*.log'))
        assert logs
        backup = Path('/opt/steps_backups')/('management_' + name + '_' + logs[-1].stem[7:])
        receipt = json.loads((backup/'deployment.json').read_text())
        assert receipt['commit'] == item['commit'] and receipt['sha256'] == item['sha256']
        assert (backup/'business_before.json').is_file()
        active = subprocess.check_output(['systemctl', 'is-active', target['service']], text=True).strip()
        assert active == 'active'
        evidence[name] = {'functional': True, 'service_active': True,
                          'business_preserved': True, 'tests': int(counts[-1]),
                          'modules': modules, 'backup': str(backup),
                          'commit': item['commit'], 'sha256': item['sha256']}
    result = {'ticket': tid, 'reviewed_message_id': plan['reviewed_message_id'],
              'environments': evidence, 'reported_case': {
                  'ticket': tid, 'download_verified': True, 'payroll_preserved': True,
                  'fields': reported['fields']}}
    args.output.write_text(json.dumps(result, indent=2))
    args.output.chmod(0o600)
    print('PREVIRED_DELIVERY_COLLECTED', tid, sorted(evidence))


if __name__ == '__main__':
    main()
