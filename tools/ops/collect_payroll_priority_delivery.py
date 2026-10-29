"""Collect exact-package T128/T135 private tests and live native UI evidence."""
import argparse
import json
from pathlib import Path
import re
import shutil


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--dev-run',required=True);p.add_argument('--sys-run',required=True)
    p.add_argument('--dev-log',required=True,type=Path);p.add_argument('--sys-log',required=True,type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    identities=set()
    for target,run,live in [('development',a.dev_run,a.dev_log),('sys',a.sys_run,a.sys_log)]:
        stage=Path('/opt/steps-validation')/('management_'+target+'_'+run)
        qa=json.loads((stage/'qa_passed.json').read_text());qa_log=Path(qa['log'])
        assert re.search(r'0 failed, 0 error\(s\) of 13 tests',qa_log.read_text())
        flow=stage/('verify-'+qa['database']+'.log');text=flow.read_text()
        assert 'MANAGEMENT_REGISTRY_OK' in text and '"native_forms_and_menu": true' in text
        if target=='sys':assert 'T135_NATIVE_OCTOBER_BATCH_OK employees=2 september_conflicts_preserved=True historical_payslips_unchanged=True rollback_required=True' in text
        served=live.read_text();assert 'MANAGEMENT_VERIFY_OK' in served
        backups=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',served);assert len(backups)==1
        deployment=Path(backups[0])/'deployment.json';deployed=json.loads(deployment.read_text())
        assert qa['commit']==deployed['commit'] and qa['release_sha256']==deployed['sha256']
        identities.add((qa['commit'],qa['release_sha256']))
        for suffix,source in [('qa.json',stage/'qa_passed.json'),('qa.log',qa_log),('clone-flow.log',flow),('live.log',live),('deployment.json',deployment)]:
            shutil.copyfile(source,a.output/(target+'-'+suffix))
    assert len(identities)==1
    commit,sha=identities.pop()
    (a.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':26,'tickets':{'128':9812,'135':9811}}))
    print('PAYROLL_PRIORITY_DELIVERY_OK')

if __name__=='__main__':main()
