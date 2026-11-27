"""Qualify the published 172-module package and budget extension together from pristine Cerro history."""
import argparse
import fcntl
import hashlib
import json
import subprocess
import tarfile

from check_cerro_budget_studio import HASHES as FIRST_OPERATIONS
from check_cerro_cold_studio import histories, NATIVE_SOURCE
from check_cerro_combined_packing import MODULES
from check_cerro_combined_studio import MODULES as STUDIO
from check_cerro_estimation_profile import snapshot
from check_cerro_packing_categories import categories
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from compare_cerro_studio_receipts import compare, receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import PRODUCT_TARGET as TARGET,PRODUCT_DEST as DEST, FINAL_TARGET, FINAL_DEST, before_guard, all_guards
from restore_cerro_studio_strict import SOURCE,module_census,sql

OPERATIONS = ROOT / 'format-shared-wizards-96887ae01b7a'
HASHES = dict(FIRST_OPERATIONS, step_cosecha='9bc8963902b1cdfe81f45a32e883fe64e5227b65a4c985fbe56e0f9906051780')
PACKAGE=ROOT/'combined-58d0cff8c320'
BUDGET = ROOT / 'budget-b31ed47840f0'
BUDGET_SHA = 'b31ed47840f07a38318e80473a76b02038a4b68d4a59d30e3ad446320bfe6885'
SHA='58d0cff8c32074c183b73ff5b317c434cc9141d291f6252ba41a331b95838b95'


def guard(mode, database):
    return json.loads(subprocess.check_output(['runuser','-u','postgres','--','/usr/bin/python3.10',
        str(ROOT/'tools/guard_cerro_studio_upgrade.py'),'--database',database,'--mode',mode],text=True))


def shared_wizard_ids(db):
    models = "('hr.entry.xls.wizard','hr.input.step.wizard','success.message')"
    result = sql(db, f"""SELECT count(*),md5(string_agg(to_jsonb(o)::text||to_jsonb(c)::text,chr(10) ORDER BY o.id))
        FROM ir_model_data o JOIN ir_model_data c ON c.module='step_hr' AND c.name=o.name
             AND c.model=o.model AND c.res_id=o.res_id
       WHERE o.module='step_cosecha'
         AND ((o.model='ir.model' AND o.res_id IN(SELECT id FROM ir_model WHERE model IN {models}))
            OR (o.model='ir.model.fields' AND o.res_id IN(SELECT id FROM ir_model_fields WHERE model IN {models})))""")
    if result.split('|')[0] != '29':
        raise ValueError('Unexpected shared payroll wizard identities in Cerro')
    return result


def main(database=TARGET, directory=DEST):
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        assert {p.name:tree_sha(p) for p in OPERATIONS.iterdir() if p.is_dir()}==HASHES
        for root,digest,count in ((PACKAGE,SHA,410),(BUDGET,BUDGET_SHA,325)):
            tar=root/'package.tar'
            assert hashlib.sha256(tar.read_bytes()).hexdigest()==digest
            with tarfile.open(tar) as archive:
                members=archive.getmembers()
                paths={p.relative_to(root).as_posix() for p in root.rglob('*')
                       if p.is_file() and p!=tar and '__pycache__' not in p.parts}
                assert len(members)==count and {m.name for m in members}==paths
                assert all(m.isfile() and (root/m.name).read_bytes()==archive.extractfile(m).read() for m in members)
        rows=histories(NATIVE_SOURCE)
        shared = shared_wizard_ids(SOURCE)
        assert histories(SOURCE)==rows
        if not (directory/'adopted-receipt.json').exists():
            before_guard(SOURCE,database,directory)
        ids=guard('arm',database)
        anchored=all_guards(database)
        opts=dict(database=database,directory=directory,roots=[BUDGET,PACKAGE,*addon_roots(database)])
        providers=sorted(set(STUDIO)|set(MODULES))
        budget = ['step_cerro_studio_budgets']
        for label,cmd,names in [
                ('adoption',['-i','step_cerro_studio_adoption'],['step_cerro_studio_adoption']),
                ('cold',['-i',','.join(providers)],providers),
                ('budget',['-i',budget[0],'-u','step_cosecha'],budget + ['step_cosecha']),
                ('warm',['-u',','.join(sorted(set(providers + budget + list(HASHES))))],
                 sorted(set(providers + budget + list(HASHES))))]:
            run('archive-'+label,cmd,**opts)
            assert guard('verify',database)==ids and all_guards(database)==anchored
            assert histories(database)==rows and shared_wizard_ids(database)==shared
            assert snapshot(SOURCE)==snapshot(database) and categories(SOURCE)==categories(database)
            census=module_census(database)
            assert not any(census[key] for key in ('pending','enterprise','non_free'))
            assert all(sql(database,"SELECT state FROM ir_module_module WHERE name='"+name+"'")=='installed' for name in names)
            raw=dict(archive_sha256=SHA,budget_sha256=BUDGET_SHA,protected=ids,views=23,census=census,shared_payroll_xmlids=shared,
                     identical_rows_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
            (directory/(label+'-archive.json')).write_text(json.dumps(raw,sort_keys=True))
        code='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        code+="from probe_cerro_studio_fullread import capture as fullread\nfrom probe_cerro_studio_navigation import capture as routes\nfrom probe_cerro_studio_client import capture as client\n"
        code+="print('BUDGET_STUDIO',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))\nenv.cr.rollback()"
        run('archive-user',[],code,**opts)
        current=receipt(directory/'archive-user.log','BUDGET_STUDIO')
        raw['matrix']=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL'),current)
        (directory/'qualified-archive.json').write_text(json.dumps(raw,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh',action='store_true')
    args=parser.parse_args()
    if args.fresh:
        main(FINAL_TARGET,FINAL_DEST)
    else:
        main()
