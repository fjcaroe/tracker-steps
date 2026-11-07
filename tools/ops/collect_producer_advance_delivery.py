"""Collect T175 exact-package, native-flow, PDF and isolation evidence."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from verify_advance_purchase_preservation import verify as verify_purchases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--console-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert re.fullmatch('[a-z0-9_]{1,24}',args.run_id)
    assert args.output.resolve().is_relative_to('/opt/steps-validation')
    assert args.console_dir.resolve().is_relative_to('/opt/steps-validation')
    args.output.mkdir(mode=0o700,exist_ok=False)
    identities=set()
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        for target in ('development','cerro','qa-cerro'):
            stage=Path('/opt/steps-validation')/('management_'+target+'_'+args.run_id)
            proof=json.loads((stage/'qa_passed.json').read_text())
            identities.add((proof['commit'],proof['release_sha256']))
            live=args.console_dir/('deploy-'+target+'.log')
            text=live.read_text()
            assert 'MANAGEMENT_VERIFY_OK' in text
            backups=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',text)
            assert len(backups)==1
            deployment=Path(backups[0])/'deployment.json'
            receipt=json.loads(deployment.read_text())
            assert (receipt['commit'],receipt['sha256'])==(proof['commit'],proof['release_sha256'])
            verify_purchases(stage)
            sources={'qa.json':stage/'qa_passed.json','qa.log':Path(proof['log']),
                     'verify.log':stage/('verify-'+proof['database']+'.log'),
                     'live.log':live,'deployment.json':deployment,
                     'purchase-preservation.json':stage/'purchase-preservation.json',
                     'pdf-review.json':args.console_dir/(target+'-pdf-review.json'),
                     'smoke.pdf':stage/'t175-smoke-advances.pdf',
                     'large.pdf':stage/'t175-large-advance.pdf'}
            for suffix,source in sources.items():shutil.copyfile(source,args.output/(target+'-'+suffix))
        assert len(identities)==1
        result=subprocess.run(['/usr/bin/python3.10','-c','from provision_cerro_qa import verify; verify()'],
            cwd=Path(__file__).resolve().parent,capture_output=True,text=True,check=True)
        text=result.stdout+result.stderr
        assert all(marker in text for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
        assert 'STEPS_PRIVATE_REPORT_' not in subprocess.check_output(['/usr/sbin/iptables','-S','OUTPUT'],text=True)
        (args.output/'isolation.log').write_text(text)
        result=subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('verify_cerro_release_pair.py')),
            '--module','step_packing_fruit_proforma','--module','step_producer_advances',
            '--output',str(args.output/'pair.json')],capture_output=True,text=True,check=True)
        assert 'CERRO_RELEASE_PAIR_OK' in result.stdout
        (args.output/'pair.log').write_text(result.stdout)
    with tarfile.open(str(args.output)+'.tar','w') as archive:
        for file in sorted(args.output.iterdir()):archive.add(file,arcname=file.name)
    Path(str(args.output)+'.tar').chmod(0o600)
    print('T175_DELIVERY_COLLECTED tests=168 '+str(args.output)+'.tar',flush=True)


if __name__=='__main__':main()
