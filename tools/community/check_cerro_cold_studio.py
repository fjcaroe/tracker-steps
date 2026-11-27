"""Install Cerro's complete qualified free catalog and BoM on a fresh source with pristine Studio history."""
import fcntl
import hashlib
import json
import subprocess

from check_cerro_combined_packing import MODULES
from check_cerro_combined_studio import HISTORY, MODULES as STUDIO
from check_cerro_estimation_profile import BRIDGE, PROFILE as ESTIMATES, snapshot
from check_cerro_packing_categories import PACKING, PRODUCER_LINK, categories
from check_cerro_studio_strict import ROOT, addon_roots, run
from compare_cerro_studio_receipts import compare, receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import COLD_TARGET, COLD_DEST, PROFILE as BOM, before_guard, all_guards
from restore_cerro_studio_strict import SOURCE, module_census, sql

NATIVE_SOURCE = 'MANAGEMENT_QA_CERRO_CUSTODY_20261126U40Q'


def histories(db):
    value=json.loads(sql(db,"""SELECT json_object_agg(v.id::text,md5(to_jsonb(v)::text)) FROM ir_ui_view v
           WHERE v.active AND EXISTS(SELECT FROM ir_model_data d WHERE d.module='studio_customization'
                   AND d.model='ir.ui.view' AND d.res_id=v.id)"""))
    assert len(value)==23
    return value


def identity_guard(mode):
    return json.loads(subprocess.check_output(['runuser','-u','postgres','--','/usr/bin/python3.10',
                 str(ROOT/'tools/guard_cerro_studio_upgrade.py'),'--database',COLD_TARGET,'--mode',mode],text=True))


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        original=histories(NATIVE_SOURCE)
        assert histories(SOURCE)==original
        if not (COLD_DEST/'adopted-receipt.json').is_file():
            before_guard(SOURCE,COLD_TARGET,COLD_DEST)
        assert histories(COLD_TARGET)==original
        ids=identity_guard('arm')
        sealed=all_guards(COLD_TARGET)
        costs=snapshot(SOURCE)
        fruit=categories(SOURCE)
        sources=[HISTORY,BOM,PRODUCER_LINK,PACKING,ESTIMATES,BRIDGE,*addon_roots(COLD_TARGET)]
        opts=dict(database=COLD_TARGET,directory=COLD_DEST,roots=sources)
        providers=sorted(set(STUDIO)|set(MODULES))
        for stage, cmd in [('adoption',['-i','step_cerro_studio_adoption']),('cold',['-i',','.join(providers)]),
                           ('warm',['-u',','.join(providers)])]:
            run('combined-'+stage,cmd,**opts)
            rows=histories(COLD_TARGET)
            different=sorted(k for k in original if original[k]!=rows[k])
            if different:
                raise ValueError('Original Studio rows changed during '+stage+': '+','.join(different))
            assert identity_guard('verify')==ids and all_guards(COLD_TARGET)==sealed
            assert (snapshot(COLD_TARGET),categories(COLD_TARGET))==(costs,fruit)
            c=module_census(COLD_TARGET)
            assert not any(c[key] for key in ('pending','enterprise','non_free'))
            result={'states':c,'whole_view_rows':23,'identical_rows_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'xml_ids':ids}
            (COLD_DEST/(stage+'-history.json')).write_text(json.dumps(result,sort_keys=True))
        body='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        body+='from probe_cerro_studio_fullread import capture as fullread\nfrom probe_cerro_studio_navigation import capture as routes\n'
        body+='from probe_cerro_studio_client import capture as client\nfrom probe_cerro_farm_directory import capture as directory\n'
        body+='from probe_cerro_shared_farms import exercise as rights\n'
        body+="print('COLD_STUDIO',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env),directory=directory(env),rights=rights(env)),sort_keys=True))\nenv.cr.rollback()"
        run('combined-user',[],body,**opts)
        current=receipt(COLD_DEST/'combined-user.log','COLD_STUDIO')
        native=receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL')
        assert current['rights']==native['rights'] and current['directory']==receipt(NATIVE/'native-directory-reference/result.log','CERRO_DIRECTORY')['directory']
        result['matrix']=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),native,current)
        (COLD_DEST/'qualified-combined.json').write_text(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
