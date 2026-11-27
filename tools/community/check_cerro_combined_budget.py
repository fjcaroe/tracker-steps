"""Qualify the published 172-module package and budget extension together from pristine Cerro history."""
import fcntl
import hashlib
import json
import subprocess
import tarfile

from check_cerro_budget_studio import OPERATIONS, HASHES
from check_cerro_cold_studio import histories, NATIVE_SOURCE
from check_cerro_combined_packing import MODULES
from check_cerro_combined_studio import MODULES as STUDIO
from check_cerro_estimation_profile import snapshot
from check_cerro_packing_categories import categories
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from compare_cerro_studio_receipts import compare, receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import PRODUCT_TARGET as TARGET,PRODUCT_DEST as DEST,before_guard,all_guards
from restore_cerro_studio_strict import SOURCE,module_census,sql

PACKAGE=ROOT/'combined-58d0cff8c320'
SHA='58d0cff8c32074c183b73ff5b317c434cc9141d291f6252ba41a331b95838b95'


def guard(mode):
    return json.loads(subprocess.check_output(['runuser','-u','postgres','--','/usr/bin/python3.10',
        str(ROOT/'tools/guard_cerro_studio_upgrade.py'),'--database',TARGET,'--mode',mode],text=True))


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        assert {p.name:tree_sha(p) for p in OPERATIONS.iterdir() if p.is_dir()}==HASHES
        tar=PACKAGE/'package.tar'
        assert hashlib.sha256(tar.read_bytes()).hexdigest()==SHA
        with tarfile.open(tar) as archive:
            members=archive.getmembers()
            paths={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p!=tar and '__pycache__' not in p.parts}
            assert len(members)==410 and {m.name for m in members}==paths
            assert all((PACKAGE/m.name).read_bytes()==archive.extractfile(m).read() for m in members)
        rows=histories(NATIVE_SOURCE)
        assert histories(SOURCE)==rows
        if not (DEST/'adopted-receipt.json').exists():
            before_guard(SOURCE,TARGET,DEST)
        ids=guard('arm')
        anchored=all_guards(TARGET)
        opts=dict(database=TARGET,directory=DEST,roots=[OPERATIONS,PACKAGE,*addon_roots(TARGET)])
        providers=sorted(set(STUDIO)|set(MODULES))
        for label,action,names in [('adoption','-i',['step_cerro_studio_adoption']),('cold','-i',providers),
                                  ('budget','-i',['step_cerro_studio_budgets']),
                                  ('warm','-u',[*providers,'step_cerro_studio_budgets'])]:
            run('archive-'+label,[action,','.join(names)],**opts)
            assert guard('verify')==ids and all_guards(TARGET)==anchored
            assert histories(TARGET)==rows
            assert snapshot(SOURCE)==snapshot(TARGET) and categories(SOURCE)==categories(TARGET)
            census=module_census(TARGET)
            assert not any(census[key] for key in ('pending','enterprise','non_free'))
            assert all(sql(TARGET,"SELECT state FROM ir_module_module WHERE name='"+name+"'")=='installed' for name in names)
            raw=dict(archive_sha256=SHA,protected=ids,views=23,census=census,
                     identical_rows_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
            (DEST/(label+'-archive.json')).write_text(json.dumps(raw,sort_keys=True))
        code='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        code+="from probe_cerro_studio_fullread import capture as fullread\nfrom probe_cerro_studio_navigation import capture as routes\nfrom probe_cerro_studio_client import capture as client\n"
        code+="print('BUDGET_STUDIO',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))\nenv.cr.rollback()"
        run('archive-user',[],code,**opts)
        current=receipt(DEST/'archive-user.log','BUDGET_STUDIO')
        raw['matrix']=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL'),current)
        (DEST/'qualified-archive.json').write_text(json.dumps(raw,sort_keys=True))


if __name__=='__main__':
    main()
