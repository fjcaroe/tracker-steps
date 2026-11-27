"""Exercise the original BoM, farm, packing, estimator and Studio screens on the same strict Cerro candidate."""
import fcntl
import hashlib
import json
import shutil
import subprocess

from check_cerro_combined_studio import HISTORY
from check_cerro_estimation_profile import BRIDGE, PROFILE as ESTIMATES, snapshot
from check_cerro_packing_categories import PACKING, PRODUCER_LINK, categories
from check_cerro_studio_strict import ROOT, addon_roots, run
from compare_cerro_studio_receipts import compare, receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import DEST, PROFILE as BOM, TARGET, all_guards
from restore_cerro_studio_strict import ESTIMATE_ROOT, SOURCE, module_census, sql

MODULES=('step_management_estimation_entry','step_cerro_studio_agriculture','step_packing','step_producers',
         'step_management_costs_producers','step_cerro_studio_transfers','step_cerro_studio_producers')


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        combined=json.loads((DEST/'combined-studio.json').read_text())
        packing=json.loads((ESTIMATE_ROOT/'packing-category-state.json').read_text())
        assert combined['updated'] and all(packing['outcome'].values())
        assert not any(module_census(TARGET)[key] for key in ('pending','enterprise','non_free'))
        assert shutil.disk_usage('/opt').free>8*1024**3
        backup=DEST/'before-combined-packing.dump'
        if not backup.is_file():
            temp=backup.with_suffix('.partial')
            with temp.open('xb') as out:
                subprocess.run(['runuser','-u','postgres','--','pg_dump','--no-tablespaces','-Fc',TARGET],stdout=out,check=True)
            subprocess.run(['pg_restore','--list',str(temp)],stdout=subprocess.DEVNULL,check=True)
            temp.rename(backup)
        before=all_guards(TARGET)
        original=(snapshot(SOURCE), categories(SOURCE))
        assert (snapshot(TARGET),categories(TARGET))==original
        opts=dict(database=TARGET,directory=DEST,roots=[HISTORY,BOM,PRODUCER_LINK,PACKING,ESTIMATES,BRIDGE,*addon_roots(TARGET)])
        try:
            run('install-combined-packing',['-i',','.join(MODULES)],**opts)
        finally:
            assert all_guards(TARGET)==before
            assert (snapshot(TARGET),categories(TARGET))==original
        census=module_census(TARGET)
        assert not any(census[key] for key in ('pending','enterprise','non_free'))
        for name in MODULES:
            assert sql(TARGET,"SELECT state FROM ir_module_module WHERE name='"+name+"'")=='installed'
        body='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        body+='from probe_cerro_bom_catalogue import exercise as bom\nfrom probe_cerro_farm_directory import capture as directory\n'
        body+='from probe_cerro_shared_farms import exercise as farm_rights\nfrom probe_cerro_studio_fullread import capture as fullread\n'
        body+='from probe_cerro_studio_navigation import capture as routes\nfrom probe_cerro_studio_client import capture as client\n'
        body+='sample='+repr(json.loads((DEST/'baseline.json').read_text()))+'\n'
        body+="print('CERRO_COMBINED_PACKING',json.dumps(dict(bom=bom(env,sample),directory=directory(env),rights=farm_rights(env),fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))\nenv.cr.rollback()"
        run('combined-packing-user',[],body,**opts)
        new=receipt(DEST/'combined-packing-user.log','CERRO_COMBINED_PACKING')
        native=receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL')
        reference=receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ')
        assert new['rights']==native['rights'] and new['directory']==receipt(NATIVE/'native-directory-reference/result.log','CERRO_DIRECTORY')['directory']
        rows=compare(reference,native,new)
        final=dict(matrix=rows,bom=new['bom'],census=census,guard_count=len(before),
                   backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest())
        (DEST/'combined-packing.json').write_text(json.dumps(final,sort_keys=True))
        print(json.dumps(census,sort_keys=True))


if __name__=='__main__':
    main()
