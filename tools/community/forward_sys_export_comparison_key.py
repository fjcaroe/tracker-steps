"""Stage the private synthetic export-comparison key directly into the new WSL RAM copy."""
import argparse
import subprocess

KEY = "/opt/steps-validation/community-sys-payroll-exports-20261126U41X3/audit.key"


def forward(qa, distro):
    # The calibration key authenticates comparisons made on synthetic QA copies.
    # It is never passed on the command line, logged, or written to workstation storage.
    recipient = """
import os,sys,hashlib,hmac
from pathlib import Path
p=Path('/dev/shm/sys-fg-193/export-comparison.key')
assert p.parent.resolve()==p.parent and (p.parent/'proofs/restored.json').is_file()
value=sys.stdin.buffer.read(33)
if len(value)!=32: raise ValueError('Expected an existing private QA comparison key')
if p.exists():
    if not hmac.compare_digest(p.read_bytes(),value): raise ValueError('Different active proof key')
else:
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400)
    with os.fdopen(fd,'wb') as out: out.write(value)
os.chown(p,61018,61018)
"""
    with subprocess.Popen(["ssh","-o","BatchMode=yes",qa,"sudo -n -u odoo cat " + KEY],stdout=subprocess.PIPE) as source:
        dest = subprocess.run(["wsl","-d",distro,"-u","root","--","python3","-c",recipient],stdin=source.stdout)
        source.stdout.close()
        if source.wait() or dest.returncode:
            raise SystemExit("The original export comparison key could not be staged")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--qa-host",required=True)
    p.add_argument("--distro",default="Ubuntu")
    a=p.parse_args()
    forward(a.qa_host,a.distro)
