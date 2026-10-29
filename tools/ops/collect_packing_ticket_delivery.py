"""Collect exact-package T132-T134 flow, prototype identities and isolation proof."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--suffix',default='5')
    a=p.parse_args();assert re.fullmatch('[a-z0-9_]{1,8}',a.suffix)
    a.output.mkdir(parents=True,exist_ok=True,mode=0o700);identities=set();pending=[]
    for target,code in [('development','d'),('cerro','c'),('qa-cerro','q')]:
        stage=Path('/opt/steps-validation')/('management_'+target+'_t132134'+code+a.suffix)
        qa=json.loads((stage/'qa_passed.json').read_text());qa_log=Path(qa['log'])
        assert re.search(r'0 failed, 0 error\(s\) of 30 tests',qa_log.read_text())
        flow=stage/('verify-'+qa['database']+'.log');text=flow.read_text()
        assert all(m in text for m in ('T132_T134_NATIVE_REPORTS_AND_HEADERS_OK','T132_WEIGHT_CORRECTION_PRESERVES_CONTAINERS_OK','T120_OPERATOR_FLOW_OK'))
        schema=stage/('packing-schema-'+qa['database']+'.json');migration=json.loads(schema.read_text())
        if target=='qa-cerro':
            assert len(migration['fields'])==4 and len(migration['views'])==2
            pending=migration['pending_dates']
        live=Path('/tmp/t132134-deploy-'+code+a.suffix+'.log');served=live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in served and 'PACKING_TICKET_SCHEMA_FINALIZE_OK' in served
        backups=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',served);assert len(backups)==1
        deployment=Path(backups[0])/'deployment.json';d=json.loads(deployment.read_text())
        assert d['commit']==qa['commit'] and d['sha256']==qa['release_sha256']
        identities.add((qa['commit'],qa['release_sha256']))
        live_schema=stage/('packing-schema-'+{'development':'LAB_TAREAS','cerro':'CERRO_EL_PLOMO','qa-cerro':'QA-CERROELPLOMO'}[target]+'.json')
        original=json.loads(live_schema.read_text())
        if target=='qa-cerro':
            assert len(original['fields'])==4 and len(original['views'])==2
            assert original['pending_dates']==pending
        for suffix,source in [('qa.json',stage/'qa_passed.json'),('qa.log',qa_log),('clone-flow.log',flow),('clone-schema.json',schema),('live-schema.json',live_schema),('live.log',live),('deployment.json',deployment)]:
            shutil.copyfile(source,a.output/(target+'-'+suffix))
    assert len(identities)==1
    isolation=subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('provision_cerro_qa.py')),'verify'],capture_output=True,text=True)
    (a.output/'qa-isolation.log').write_text(isolation.stdout+isolation.stderr)
    assert isolation.returncode==0 and all(m in isolation.stdout for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    commit,sha=identities.pop()
    (a.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':90,'pending_dates':pending,'tickets':{'132':9794,'133':9802,'134':9807}}))
    print('PACKING_TICKET_DELIVERY_OK pending_dates='+str(len(pending)))

if __name__=='__main__':main()
