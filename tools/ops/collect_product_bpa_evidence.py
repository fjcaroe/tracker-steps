"""Collect T127 immutable proofs outside Git; never copies credentials/dumps."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    root=Path('/opt/steps-validation')
    versions={}
    for target,run,log,database in [('development','t127d4','d','LAB_TAREAS'),('cerro','t127c','c','CERRO_EL_PLOMO'),('qa-cerro','t127q','q','QA-CERROELPLOMO')]:
        stage=root/('management_'+target+'_'+run)
        proof=json.loads((stage/'qa_passed.json').read_text())
        deploy=Path('/tmp/t127-deploy-'+log+'.log')
        text=deploy.read_text();assert 'MANAGEMENT_VERIFY_OK' in text
        matches=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',text);assert len(matches)==1
        backup=Path(matches[0]);assert backup.parent==Path('/opt/steps_backups')
        sources={target+'-qa.json':stage/'qa_passed.json',target+'-qa.log':Path(proof['log']),
            target+'-clone-flow.log':stage/('verify-'+proof['database']+'.log'),
            target+'-live.log':deploy,target+'-deployment.json':backup/'deployment.json'}
        for name,source in sources.items():shutil.copyfile(source,a.output/name)
        before=json.loads((stage/'business_before.json').read_text())
        versions[target]={'original_aptitudes':before.get('x_aptitud_plaguicidas', [0])[0]}
        if target=='development':
            assert versions[target]['original_aptitudes']==63
    community=root/'BPA_COMMUNITY_t127oss2'/'passed.json'
    community_proof=json.loads(community.read_text())
    tested=root/'management_development_t127d4'/'addons'
    release=json.loads((tested/'release.json').read_text())
    core={name:hashlib.sha256((tested/name).read_bytes()).hexdigest() for name in release['files'] if name.startswith('step_product_bpa/')}
    assert core=={name:value for name,value in release['files'].items() if name.startswith('step_product_bpa/')}
    community_proof.update({'package_commit':release['commit'],'core_source_files':core})
    (a.output/'community.json').write_text(json.dumps(community_proof,indent=2))
    result=subprocess.run(['/usr/bin/python3.10',str(Path(__file__).with_name('provision_cerro_qa.py')),'verify'],text=True,capture_output=True)
    (a.output/'qa-final-isolation.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0
    registry=json.loads((a.output/'development-deployment.json').read_text())
    (a.output/'delivery-reviewed.json').write_text(json.dumps({'127':{'commit':registry['commit'],'sha256':registry['sha256'],'reviewed_message_id':9756}}))
    (a.output/'preservation-summary.json').write_text(json.dumps(versions,indent=2))
    print('T127_EVIDENCE_COLLECTED '+json.dumps(versions))

if __name__=='__main__':main()
