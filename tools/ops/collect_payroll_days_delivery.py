"""Collect T138 exact-package four-destination and real unpaid-case proofs."""
import argparse
import json
from pathlib import Path
import re
import shutil


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True,mode=0o700);identities=set();count=0
    for target,code in [('development','d'),('sys','s'),('demo-sys','m'),('cerro','c')]:
        stage=Path('/opt/steps-validation')/('management_'+target+'_t138'+code+'2')
        qa_file=stage/'qa_passed.json';qa=json.loads(qa_file.read_text());test=Path(qa['log'])
        matches=re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database',test.read_text())
        assert matches and int(matches[-1])==7;count+=int(matches[-1])
        flow=stage/('verify-'+qa['database']+'.log')
        if target=='sys':assert 'T138_NATIVE_CASES_OK one_absence=29 two_absences=28 paid_history_unchanged=True rollback_required=True' in flow.read_text()
        live=Path('/tmp/t138-deploy-'+code+'2.log');text=live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in text
        if target=='demo-sys':assert 'DEMO_SYS_SCOPE_OK' in text
        backup=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',text);assert len(backup)==1
        deployment=Path(backup[0])/'deployment.json';d=json.loads(deployment.read_text())
        assert d['commit']==qa['commit'] and d['sha256']==qa['release_sha256']
        identities.add((qa['commit'],qa['release_sha256']))
        for suffix,source in [('qa.json',qa_file),('qa.log',test),('flow.log',flow),('live.log',live),('deployment.json',deployment)]:
            shutil.copyfile(source,args.output/(target+'-'+suffix))
    assert len(identities)==1;commit,sha=identities.pop()
    (args.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':count,'reviewed_message_id':9841}))
    print('T138_DELIVERY_COLLECTED tests='+str(count))


if __name__=='__main__':main()
