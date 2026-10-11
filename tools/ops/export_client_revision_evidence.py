"""Export synthetic T63-T67 samples and logs, excluding databases and credentials."""
import argparse
import os
from pathlib import Path
import pwd
import re
import tarfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'));p.add_argument('run_id')
a=p.parse_args();assert os.geteuid()==0 and re.fullmatch('[a-z0-9_]{1,24}',a.run_id)
owner=pwd.getpwnam(os.environ['SUDO_USER'])
stage=Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.run_id)
out=Path('/tmp')/('t6367-evidence-'+a.environment+'-'+a.run_id+'.tar.gz')
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as stream,tarfile.open(fileobj=stream,mode='w:gz') as archive:
    for name in ('action_sale_note.pdf','action_proforma.pdf','qa_passed.json'):
        archive.add(stage/name,arcname=name)
    for file in stage.glob('verify-*.log'):
        archive.add(file,arcname=file.name)
os.chown(out,owner.pw_uid,owner.pw_gid)
print('CLIENT_REVISION_EVIDENCE_OK',out)
