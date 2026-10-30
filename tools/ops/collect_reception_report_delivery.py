"""Collect exact-package T141 proofs and verify customer-QA isolation."""
import argparse
import hashlib
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
        stage = Path('/opt/steps-validation') / ('management_' + target + '_t141' + code + args.suffix)
        qa = json.loads((stage / 'qa_passed.json').read_text())
        test = Path(qa['log']); matches = re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database', test.read_text())
        assert matches and int(matches[-1]) >= 8
        count += int(matches[-1])
        flow = stage / ('verify-' + qa['database'] + '.log')
        assert 'MANAGEMENT_REGISTRY_OK' in flow.read_text()
        assert 'T141_NATIVE_PDF_OK' in flow.read_text()
        if target=='qa-cerro':
            assert 'T141_REPORTED_RECEIPT_PDF_OK weights_unchanged=True' in flow.read_text()
            assert 'CUSTOMER_QA_REPORT_LOOPBACK_REMOVED' in Path('/tmp/t141-qa-q'+args.suffix+'.log').read_text()
        review_path=Path(__file__).resolve().parents[2]/('review-'+target+'.json')
        review=json.loads(review_path.read_text(encoding='utf-8-sig'))
        assert review['reviewed'] is True
        for name,item in review['files'].items():
            assert name in ('receipt-short.pdf','receipt-long.pdf','receipt-reported.pdf')
            source=stage/'data'/name
            assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sha256']
            shutil.copyfile(source,args.output/(target+'-'+name))
        shutil.copyfile(review_path,args.output/(target+'-visual-review.json'))
        live = Path('/tmp/t141-deploy-' + code + args.suffix + '.log')
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
        print('T141_WAITING_FINAL_ISOLATION_LEASE',flush=True)
        fcntl.flock(lock,fcntl.LOCK_EX)
        capture = subprocess.run(['/usr/bin/python3.10', '-c', 'from provision_cerro_qa import verify; verify()'],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True, check=True)
        text = capture.stdout + capture.stderr
        assert all(m in text for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
        assert 'STEPS_PRIVATE_REPORT_' not in subprocess.check_output(['/usr/sbin/iptables','-S','OUTPUT'],text=True)
        (args.output/'isolation.log').write_text(text)
        result = subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('verify_cerro_release_pair.py')),
            '--module','step_packing_reception_report','--output',str(args.output/'pair.json')],capture_output=True,text=True,check=True)
        assert 'CERRO_RELEASE_PAIR_OK' in result.stdout
        (args.output/'pair.log').write_text(result.stdout)
    commit,sha=identities.pop()
    (args.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':count,'reviewed_messages':{'141':9863}}))
    print('T141_DELIVERY_COLLECTED tests='+str(count))


if __name__=='__main__':main()
