"""Collect T137 exact-package tests, native flow and destination isolation."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from manage_management import query


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('--suffix',default='3');parser.add_argument('--development-suffix',default='2')
    args=parser.parse_args();args.output.mkdir(mode=0o700,parents=True,exist_ok=True)
    assert all(re.fullmatch('[a-z0-9]{1,8}',s) for s in (args.suffix,args.development_suffix))
    identities=set();count=0;pending=None
    for target,code in [('development','d'),('cerro','c'),('qa-cerro','q')]:
        suffix=args.development_suffix if target=='development' else args.suffix
        stage=Path('/opt/steps-validation')/('management_'+target+'_t137'+code+suffix)
        proof=stage/'qa_passed.json';qa=json.loads(proof.read_text())
        test=Path(qa['log']);text=test.read_text()
        matches=re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database',text)
        assert matches;count+=int(matches[-1])
        flow=stage/('verify-'+qa['database']+'.log');native=flow.read_text()
        assert 'T137_PREVALIDATED_OUTPUT_NATIVE_CLOSE_OK no_duplicate_stock=True' in native
        if target=='qa-cerro':
            assert 'T137_REPORTED_QUADRATURE_OK' in native
            pending='pending_product_inventory=True' in native
        if target in ('cerro','qa-cerro'):
            assert 'T137_INVENTORY_DEFINITION_TESTED no_stock_created=True' in native
        live=Path('/tmp/t137-deploy-'+code+suffix+'.log');served=live.read_text()
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
    plan=json.loads((Path(__file__).resolve().parents[2]/'packing-replay.json').read_text())
    code=plan['product_code'];assert re.fullmatch('[A-Za-z0-9_-]+',code)
    active={}
    for database in ('CERRO_EL_PLOMO','QA-CERROELPLOMO'):
        flags=query(database,"SELECT t.is_storable FROM product_product p JOIN product_template t ON t.id=p.product_tmpl_id WHERE p.default_code='%s'"%code)
        assert flags=='t','Active inventory definition must match the human decision'
        active[database]=True
    (args.output/'active-inventory.json').write_text(json.dumps(active))
    commit,sha=identities.pop()
    (args.output/'delivery.json').write_text(json.dumps({'commit':commit,'sha256':sha,'tests':count,'pending_product_inventory':pending,'reviewed_message_id':9837}))
    print('T137_DELIVERY_COLLECTED tests=%s pending_product_inventory=%s'%(count,pending))


if __name__=='__main__':main()
