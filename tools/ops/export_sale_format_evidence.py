"""Export only synthetic report samples and verification logs to the SSH caller."""
import argparse
import os
from pathlib import Path
import pwd
import re
import tarfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('environment', choices=('development', 'cerro'))
p.add_argument('run_id')
a = p.parse_args()
assert re.fullmatch('[a-z0-9_]{1,24}', a.run_id) and os.geteuid() == 0
owner = pwd.getpwnam(os.environ['SUDO_USER'])
stage = Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.run_id)
output = Path('/tmp')/('t62-evidence-'+a.environment+'-'+a.run_id+'.tar.gz')
fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'wb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
    for name in ('action_proforma.pdf', 'action_sale_note.pdf', 'multipage.pdf'):
        archive.add(stage/name, arcname=name)
    for file in stage.glob('verify-*.log'):
        archive.add(file, arcname=file.name)
    if (stage/'qa_passed.json').exists():
        archive.add(stage/'qa_passed.json', arcname='qa_passed.json')
os.chown(output, owner.pw_uid, owner.pw_gid)
print('EVIDENCE_EXPORT_OK', output)
