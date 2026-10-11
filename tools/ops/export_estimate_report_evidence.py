"""Export T68 synthetic checks only; never dumps or configuration."""
import argparse,os,pwd,re,tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'));p.add_argument('run_id')
p.add_argument('--phase',choices=('qa','live'),default='qa')
a=p.parse_args();assert os.geteuid()==0 and re.fullmatch('[a-z0-9_]{1,24}',a.run_id)
owner=pwd.getpwnam(os.environ['SUDO_USER'])
stage=Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.run_id)
out=Path('/tmp')/('t68-evidence-'+a.environment+'-'+a.run_id+'-'+a.phase+'.tar.gz')
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as stream,tarfile.open(fileobj=stream,mode='w:gz') as archive:
    archive.add(stage/'qa_passed.json',arcname='qa_passed.json')
    for file in [*stage.glob('qa-*.log'),*stage.glob('verify-*.log')]:
        archive.add(file,arcname=file.name)
os.chown(out,owner.pw_uid,owner.pw_gid)
print('ESTIMATE_REPORT_EVIDENCE_OK',out)
