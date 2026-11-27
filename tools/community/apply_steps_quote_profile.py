"""Apply the qualified Steps sales form migration to an admitted, idle private CRM restore."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from prepare_steps_crm_cohort import SOURCE_MANIFESTS
from restore_sys_previred_pair import LOCK, require


def apply(folder):
    require(folder.resolve(strict=True) == folder and folder.is_relative_to('/opt/steps-validation'),
            'private-steps-restore-directory-required')
    proof = json.loads((folder/'preservation.json').read_bytes())
    plan = json.loads((folder/'plan.json').read_bytes())
    db = proof['community']
    require(re.fullmatch(r'COMMUNITY_STEPS_CRM_QUOTE_[A-Z0-9_]+', db) and
            proof['original'] == db.replace('COMMUNITY_','MANAGEMENT_QA_',1) and plan['database'] == db and
            proof['preserved_tables_and_schema'] and proof['preserved_counters'] and
            proof['source_dump_sha256'] == '8247457c4469d314fb3eeb44202604a1c294cfa374d426f30f31c9a16144f7ca'
            and proof['manifest_sha256'] == SOURCE_MANIFESTS, 'unrecognized-steps-quotation-source')
    script = """
import json,sys,psycopg2
data=json.load(sys.stdin)
sys.path.insert(0,data['code'])
from check_steps_crm_preservation import compare
from check_steps_quote_form_storage import check
with psycopg2.connect(dbname=data['community'],host='/var/run/postgresql') as conn:
    ui=check(conn,data['community'])
report=compare(data['native'],data['community'],data['plan'])
print(json.dumps({'ui':ui,'sql':report}))
"""
    payload = {'native': proof['original'], 'community': db, 'plan': plan,
               'code': str(Path(__file__).resolve().parent)}
    output = subprocess.check_output(['runuser','-u','postgres','--',sys.executable,'-B','-c',script],
                                     input=json.dumps(payload).encode())
    result = json.loads(output)
    differences = result['sql']['differences']
    require(not result['sql']['unexpected_modules'] and differences['public_tables'] ==
            ['ir_module_module','ir_ui_menu','ir_ui_view'] and
            not any(keys for category, keys in differences.items() if category != 'public_tables'),
            'unqualified-change-to-the-fresh-private-quotation-profile')
    path = folder/'quotation-forms.json'
    if path.exists():
        old = json.loads(path.read_bytes())
        require(old['sql'] == result['sql'] and not result['ui']['differences']['public_tables'],
                'previous-quotation-acceptance-changed')
    else:
        with path.open('x',encoding='utf-8') as report:
            json.dump(result,report,indent=2)
    print(json.dumps({'database':db,'archived_views':result['ui']['inactive_views'],
                      'saved_workbooks':0, 'original_counters':result['ui']['original_counters']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        apply(args.folder)
