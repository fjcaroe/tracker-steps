"""Collect private same-package T130 company-form delivery and isolation proofs."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--ticket',type=int,choices=(130,131),default=130);a=p.parse_args()
    test_count=13 if a.ticket==131 else 11
    run_prefix='t131' if a.ticket==131 else 't130'
    run_tail='' if a.ticket==131 else '5'
    a.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    packages=set()
    for target,suffix in [('development','d'),('cerro','c'),('qa-cerro','q')]:
        stage=Path('/opt/steps-validation')/('management_'+target+'_'+run_prefix+suffix+run_tail)
        proof=json.loads((stage/'qa_passed.json').read_text())
        qa=Path(proof['log']);assert re.search(r'0 failed, 0 error\(s\) of %s tests'%test_count,qa.read_text())
        live=Path('/tmp/'+run_prefix+'-deploy-'+suffix+'.log');text=live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in text and '"compact_actions_preserved": true' in text
        backups=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',text);assert len(backups)==1
        deployment=Path(backups[0])/'deployment.json'
        installed=json.loads(deployment.read_text())
        assert proof['commit']==installed['commit'] and proof['release_sha256']==installed['sha256']
        packages.add((proof['commit'],proof['release_sha256']))
        flow=stage/('verify-'+proof['database']+'.log')
        assert 'T130_NATIVE_COMPANY_FORM_FLOW_OK rollback_required=True' in flow.read_text()
        if a.ticket==131:assert 'T131_NATIVE_BRANCH_FLOW_OK generated_contact=True rollback_required=True' in flow.read_text()
        for name,source in {'qa.json':stage/'qa_passed.json','qa.log':qa,'clone-flow.log':flow,'live.log':live,'deployment.json':deployment}.items():
            shutil.copyfile(source,a.output/(target+'-'+name))
    assert len(packages)==1
    isolation=subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('provision_cerro_qa.py')),'verify'],capture_output=True,text=True)
    (a.output/'qa-isolation.log').write_text(isolation.stdout+isolation.stderr)
    assert isolation.returncode==0
    assert all(marker in isolation.stdout for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    (a.output/'delivery.json').write_text(json.dumps({'commit':next(iter(packages))[0],'sha256':next(iter(packages))[1],'destinations':3,'test_executions':3*test_count,'native_company_form':True,'compact_actions_preserved':True},indent=2))
    (a.output/'delivery-reviewed.json').write_text(json.dumps({str(a.ticket):{'commit':next(iter(packages))[0],'sha256':next(iter(packages))[1],'reviewed_message_id':9790 if a.ticket==131 else 9777}}))
    print('COMPANY_FORM_DELIVERY_EVIDENCE_OK ticket='+str(a.ticket))

if __name__=='__main__':main()
