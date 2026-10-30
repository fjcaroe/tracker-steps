"""Collect exact-package T139/T140 proofs and verify customer-QA isolation."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--suffix', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[1-9][0-9]*', args.suffix)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    identities = set(); count = 0
    for target, code in [('development','d'),('cerro','c'),('qa-cerro','q')]:
        stage = Path('/opt/steps-validation') / ('management_' + target + '_t139' + code + args.suffix)
        qa = json.loads((stage / 'qa_passed.json').read_text())
        test = Path(qa['log']); matches = re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database', test.read_text())
        assert matches and int(matches[-1]) >= 10
        count += int(matches[-1])
        flow = stage / ('verify-' + qa['database'] + '.log')
        assert 'MANAGEMENT_REGISTRY_OK' in flow.read_text()
        live = Path('/tmp/t139-deploy-' + code + args.suffix + '.log')
        assert 'MANAGEMENT_VERIFY_OK' in live.read_text()
        backup = re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)', live.read_text())
        assert len(backup) == 1
        deployment = Path(backup[0]) / 'deployment.json'
        applied = json.loads(deployment.read_text())
        assert applied['commit'] == qa['commit'] and applied['sha256'] == qa['release_sha256']
        identities.add((qa['commit'],qa['release_sha256']))
        for suffix, source in [('qa.json',stage/'qa_passed.json'),('qa.log',test),('flow.log',flow),('live.log',live),('deployment.json',deployment)]:
            shutil.copyfile(source,args.output/(target+'-'+suffix))
    assert len(identities) == 1
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('T139_WAITING_FINAL_ISOLATION_LEASE',flush=True)
        fcntl.flock(lock,fcntl.LOCK_EX)
        capture = subprocess.run(['/usr/bin/python3.10', '-c', 'from provision_cerro_qa import verify; verify()'],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True, check=True)
        text = capture.stdout + capture.stderr
        assert all(m in text for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
        (args.output/'isolation.log').write_text(text)
        result = subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('verify_cerro_release_pair.py')),
            '--module','step_agriculture_multicompany','--output',str(args.output/'pair.json')],capture_output=True,text=True,check=True)
        assert 'CERRO_RELEASE_PAIR_OK' in result.stdout
        (args.output/'pair.log').write_text(result.stdout)
    commit,sha=identities.pop()
    (args.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':count,'reviewed_messages':{'139':9849,'140':9853}}))
    print('T139_T140_DELIVERY_COLLECTED tests='+str(count))


if __name__=='__main__':main()
