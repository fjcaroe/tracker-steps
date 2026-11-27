"""Run the original SyS managers' leave workflow only on the isolated memory-based derivative."""
import json
from pathlib import Path
import subprocess
import sys

from inspect_sys_absence_chain import TARGET,U47
from seal_local_sys_193 import MEM,PORT,SOCKET


def run():
    tools=Path(__file__).resolve().parent
    if not json.loads((U47/"native-and-product.json").read_bytes())["all_projections_match"]:
        raise ValueError("Native SQL equivalence is required before testing the original approvers")
    conf=U47/"odoo.conf"
    conf.write_text("[options]\nlist_db = False\ndb_user = odoo\ndb_host = "+SOCKET+"\ndb_port = "+str(PORT)+"\nlog_level = warn\n")
    source=(tools/"probe_sys_absence_approvers.py").read_text()+"\nprint('SYS_LEAVE '+json.dumps(run(env)),flush=True)\n"
    command=[sys.executable,str(tools/"run_focal_print_command.py"),"--user","odoo","--","python3.10",
             "/work/sys-fg-code/odoo-bin","shell","-c",str(conf),"-d",TARGET,"--db-filter=^"+TARGET+"$",
             "--addons-path="+str(MEM/"overlay")+",/work/sys-fg-code/addons,/work/sys-fg-code/odoo/addons",
             "--data-dir="+str(U47/"data"),"--no-http","--max-cron-threads=0","--workers=0","--stop-after-init","--load=base,web"]
    with (U47/"functional.stderr").open("wb") as err:
        proc=subprocess.run(command,input=source.encode(),stdout=subprocess.PIPE,stderr=err)
    if proc.returncode:
        raise SystemExit("Private leave scenario failed; see the private traceback")
    found=[json.loads(line[10:]) for line in proc.stdout.splitlines() if line.startswith(b"SYS_LEAVE ")]
    if len(found)!=1:
        raise ValueError("An actual approver result was expected")
    (U47/"functional.json").write_text(json.dumps(found[0],sort_keys=True))
    print("Completed manager flows",len(found[0]["approver_forms"]))


if __name__=="__main__":
    run()
