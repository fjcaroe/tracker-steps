"""Collect private same-package manual-contact delivery and isolation proofs."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    packages=set()
    for target,suffix in [('development','d'),('cerro','c'),('qa-cerro','q')]:
        stage=Path('/opt/steps-validation')/('management_'+target+'_mc_'+suffix)
        proof=json.loads((stage/'qa_passed.json').read_text())
        qa=Path(proof['log']);assert re.search(r'0 failed, 0 error\(s\) of 4 tests',qa.read_text())
        live=Path('/tmp/mc-deploy-'+suffix+'.log');text=live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in text and '"paid_autocomplete_disabled": true' in text
        backups=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',text);assert len(backups)==1
        deployment=Path(backups[0])/'deployment.json'
        installed=json.loads(deployment.read_text())
        assert proof['commit']==installed['commit'] and proof['release_sha256']==installed['sha256']
        packages.add((proof['commit'],proof['release_sha256']))
        flow=stage/('verify-'+proof['database']+'.log')
        assert 'MANUAL_CONTACT_OPERATOR_FLOW_OK rollback_required=True' in flow.read_text()
        for name,source in {'qa.json':stage/'qa_passed.json','qa.log':qa,'clone-flow.log':flow,'live.log':live,'deployment.json':deployment}.items():
            shutil.copyfile(source,a.output/(target+'-'+name))
    assert len(packages)==1
    isolation=subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('provision_cerro_qa.py')),'verify'],capture_output=True,text=True)
    (a.output/'qa-isolation.log').write_text(isolation.stdout+isolation.stderr)
    assert isolation.returncode==0
    assert all(marker in isolation.stdout for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    (a.output/'delivery.json').write_text(json.dumps({'commit':next(iter(packages))[0],'sha256':next(iter(packages))[1],'destinations':3,'test_executions':12,'external_enrichment_disabled':True,'local_search_preserved':True},indent=2))
    print('MANUAL_CONTACT_DELIVERY_EVIDENCE_OK')

if __name__=='__main__':main()
