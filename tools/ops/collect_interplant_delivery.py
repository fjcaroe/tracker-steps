"""Collect immutable T207/T208 publication evidence; never alter business data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

TARGETS = ('development', 'cerro', 'qa-cerro')


def server(args):
    import fcntl
    from manage_management import tree_hash, query
    import configparser
    root = Path(__file__).resolve().parent
    registry = json.loads((root/'environments.json').read_text())['environments']
    with tarfile.open(args.release) as archive:
        versions = json.load(archive.extractfile('release.json'))['versions']
    assert set(versions) == {'step_packing_interplant','step_packing_ticket_revision'}
    result = {'versions':versions, 'sha256':hashlib.sha256(args.release.read_bytes()).hexdigest(), 'targets':{}, 'tests':0}
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for target in TARGETS:
            entry = registry[target]
            stage = Path('/opt/steps-validation') / ('management_' + target + '_' + args.run_id)
            qa = json.loads((stage/'qa_passed.json').read_text())
            assert qa['release_sha256'] == result['sha256']
            result.setdefault('commit', qa['commit'])
            assert result['commit'] == qa['commit']
            counts = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests', Path(qa['log']).read_text())
            assert counts and int(counts[-1]) >= (22 if versions['step_packing_interplant'] != '18.0.1.0.0' else 19)
            result['tests'] += int(counts[-1])
            copy_log = (stage/('verify-' + qa['database'] + '.log')).read_text()
            live_log = (stage/('verify-' + entry['database'] + '.log')).read_text()
            for text in (copy_log, live_log):
                assert 'INTERPLANT_REGISTRY_OK ' in text and 'MANAGEMENT_REGISTRY_OK ' in text
                assert 'Traceback (most recent call last)' not in text
            if target == 'cerro':
                match = re.search(r'INTERPLANT_CUSTOMER_COPY_OK (.+)', copy_log)
                assert match
                case = json.loads(match[1])
                assert case['pending_before_validation'] and case['owners_lots_stock_conserved']
                assert set(case['kinds']) == {'C','E','N'} and case['excluded_kilos'] == 799.5
                result['customer_case'] = case
            matches = []
            for backup in Path('/opt/steps_backups').glob('management_' + target + '_*'):
                receipt = backup/'deployment.json'
                if receipt.is_file():
                    deployed = json.loads(receipt.read_text())
                    if deployed['sha256'] == result['sha256']:
                        matches.append((backup, deployed))
            assert len(matches) == 1, 'Expected one matching deployment receipt for ' + target
            backup, deployed = matches[0]
            assert deployed['commit'] == result['commit']
            subprocess.run(['pg_restore','--list',str(backup/'database.dump')],check=True,stdout=subprocess.DEVNULL)
            config = configparser.ConfigParser(interpolation=None); config.read(entry['config'])
            assert config['options']['db_name'] == entry['database']
            roots = [Path(p.strip()) for p in config['options']['addons_path'].split(',')]
            modules = {}
            for name, version in versions.items():
                actual = query(entry['database'], "SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'" % name)
                assert actual == version
                source = next(p/name for p in roots if (p/name/'__manifest__.py').is_file())
                assert source.resolve() == Path(deployed['overlay'])/name
                modules[name] = {'version':actual,'sha256':tree_hash(source)}
            subprocess.run(['systemctl','is-active','--quiet',entry['service']],check=True)
            result['targets'][target] = {'deployed':True,'version_form_menu_flow':True,
                'backup':str(backup),'backup_readable':True,'sha256':result['sha256'],
                'qa_log':qa['log'],'modules':modules}
        reference = result['targets']['development']['modules']
        assert all(row['modules'] == reference for row in result['targets'].values())
        result['parity'] = True
        # Verify only: no refresh, firewall/config changes or outbound messages.
        isolation = subprocess.run(['python3','-c','from provision_cerro_qa import verify; verify()'],
            cwd=root,text=True,capture_output=True,check=True)
        for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'):
            assert marker in isolation.stdout
        result['qa_isolation'] = True
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('INTERPLANT_DELIVERY_EVIDENCE_OK ' + str(args.output))


def finalize(args):
    result = json.loads((args.directory/'server-evidence.json').read_text(encoding='utf-8-sig'))
    assert hashlib.sha256((args.directory/'release.tar.gz').read_bytes()).hexdigest() == result['sha256']
    for target in TARGETS:
        ui = json.loads((args.directory/target/'ui-result.json').read_text(encoding='utf-8'))
        assert all(ui[k] for k in ('currentReceiptFilter','receptionPivot','interplantMenu','typeBeforeRecipient'))
        assert not ui['errors']
        if args.ticket == 209:
            destination_ui = json.loads((args.directory/target/'destination-ui-result.json').read_text(encoding='utf-8'))
            assert destination_ui['destinationWarehouseChoices'] and destination_ui['sourceCompanyUnchanged'] and not destination_ui['errors']
    tickets = json.loads((args.directory/'open-before-close.json').read_text(encoding='utf-8'))
    result['reviewed_messages'] = {}
    for ticket in tickets:
        if ticket['id'] in ((args.ticket,) if args.ticket else (207,208)):
            ids = [m['id'] for m in ticket['messages'] if m['message_type'] in ('comment','email')]
            result['reviewed_messages'][str(ticket['id'])] = max(ids)
    reviewed = {str(args.ticket):args.reviewed_message} if args.ticket else {'207':10408,'208':10411}
    assert result['reviewed_messages'] == reviewed, 'Read new responses before delivery'
    result['complete'] = True
    (args.directory/'delivery.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('INTERPLANT_DELIVERY_FINALIZED tests=' + str(result['tests']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode',required=True)
    p = commands.add_parser('server'); p.add_argument('release',type=Path); p.add_argument('run_id'); p.add_argument('output',type=Path)
    p = commands.add_parser('finalize'); p.add_argument('directory',type=Path); p.add_argument('--ticket',type=int,choices=(209,)); p.add_argument('--reviewed-message',type=int)
    args = parser.parse_args()
    if args.mode == 'server':
        assert re.fullmatch(r't20[79][a-z]+',args.run_id)
        server(args)
    else:
        finalize(args)
