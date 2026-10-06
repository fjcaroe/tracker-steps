"""Package only committed support connector files, outside the public checkout."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path);args=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    modules=['step_helpdesk_whatsapp','step_project_agriculture_scope']
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,*modules],cwd=root,text=True).splitlines()
    files={name:subprocess.check_output(['git','show',commit+':'+name],cwd=root).replace(b'\r\n',b'\n') for name in names}
    assert files and all('__pycache__' not in n and not n.endswith('.pyc') for n in files)
    version=ast.literal_eval(files['step_helpdesk_whatsapp/__manifest__.py'].decode())['version']
    versions={n:ast.literal_eval(files[n+'/__manifest__.py'].decode())['version'] for n in modules}
    proof={'commit':commit,'module':'step_helpdesk_whatsapp','version':version,'versions':versions,'files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    files['release.json']=json.dumps(proof).encode()
    with tarfile.open(args.output,'w:gz') as archive:
        for name,data in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
            archive.addfile(info,io.BytesIO(data))
    print(json.dumps({'commit':commit,'version':version,'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
