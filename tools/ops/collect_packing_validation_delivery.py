"""Collect T137 exact-package tests, native flow and destination isolation."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    args=parser.parse_args();args.output.mkdir(mode=0o700,parents=True,exist_ok=True)
    identities=set();count=0;pending=None
    for target,code in [('development','d'),('cerro','c'),('qa-cerro','q')]:
        stage=Path('/opt/steps-validation')/('management_'+target+'_t137'+code+'1')
        proof=stage/'qa_passed.json';qa=json.loads(proof.read_text())
        test=Path(qa['log']);text=test.read_text()
        matches=re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database',text)
        assert matches;count+=int(matches[-1])
        flow=stage/('verify-'+qa['database']+'.log');native=flow.read_text()
        assert 'T137_PREVALIDATED_OUTPUT_NATIVE_CLOSE_OK no_duplicate_stock=True' in native
        if target=='qa-cerro':
            assert 'T137_REPORTED_QUADRATURE_OK' in native
            pending='pending_product_inventory=True' in native
        live=Path('/tmp/t137-deploy-'+code+'1.log');served=live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in served
        backups=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',served);assert len(backups)==1
        deployment=Path(backups[0])/'deployment.json';d=json.loads(deployment.read_text())
        assert d['commit']==qa['commit'] and d['sha256']==qa['release_sha256']
        identities.add((qa['commit'],qa['release_sha256']))
        for suffix,source in [('qa.json',proof),('qa.log',test),('flow.log',flow),('live.log',live),('deployment.json',deployment)]:
            shutil.copyfile(source,args.output/(target+'-'+suffix))
    assert len(identities)==1 and pending is not None
    isolation=subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('provision_cerro_qa.py')),'verify'],capture_output=True,text=True)
    assert isolation.returncode==0 and all(marker in isolation.stdout for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    (args.output/'isolation.log').write_text(isolation.stdout+isolation.stderr)
    commit,sha=identities.pop()
    (args.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':count,'pending_product_inventory':pending,'reviewed_message_id':9837}))
    print('T137_DELIVERY_COLLECTED tests=%s pending_product_inventory=%s'%(count,pending))


if __name__=='__main__':main()
