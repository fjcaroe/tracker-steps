"""Prove the combined strict BoM, original farm paths and shared catalogues before and after updating the owners."""
import fcntl
import json
import subprocess

from check_cerro_studio_strict import ROOT, addon_roots, run
from restore_cerro_bom_before_guard import DEST, PROFILE, TARGET, all_guards
from restore_cerro_studio_strict import module_census, sql

MODULES = ('step_agriculture_core', 'step_agriculture_farm_directory', 'step_agriculture_shared_farms',
           'step_cerro_studio_farms', 'step_packing_process_catalog', 'step_packing_process_category',
           'step_cerro_studio_process_types', 'step_agriculture_species_pallet', 'step_species_tariff',
           'step_cerro_studio_species', 'step_cerro_product_account_views', 'step_cerro_studio_companies',
           'step_cerro_bom_company')


def controls(label):
    body = 'import json,sys\nsys.path.insert(0,' + repr(str(ROOT / 'tools')) + ')\n'
    body += """from probe_cerro_shared_farms import capture as farms, exercise as farm_rights
from probe_cerro_farm_directory import capture as directory
from probe_cerro_legacy_aliases import capture as aliases
from probe_cerro_species_pallet import capture as species
from probe_cerro_process_category import capture as processes
from probe_cerro_studio_fullread import capture as fullread
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_bom_catalogue import reference as boms
print('COMBINED_STUDIO',json.dumps(dict(farms=farms(env),rights=farm_rights(env),directory=directory(env),
    species=species(env,test=True),process=processes(env,test=True),boms=boms(env),fullread=fullread(env),
    routes=routes(env),aliases=aliases(env)),sort_keys=True))
env.cr.rollback()
"""
    run(label, [], body, database=TARGET, directory=DEST, roots=[PROFILE, *addon_roots(TARGET)])
    text = (DEST / (label + '.log')).read_text()
    result, = [json.loads(l.split(' ',1)[1]) for l in text.splitlines() if l.startswith('COMBINED_STUDIO ')]
    return result


def guard(mode):
    return json.loads(subprocess.check_output(['runuser','-u','postgres','--','/usr/bin/python3.10',
              str(ROOT / 'tools/guard_cerro_studio_upgrade.py'), '--database', TARGET, '--mode', mode], text=True))


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        assert (DEST / 'qualified-bom.json').is_file()
        baseline_census = module_census(TARGET)
        assert not any(baseline_census[k] for k in ('enterprise','non_free','pending'))
        original_guards = all_guards(TARGET)
        armed = guard('arm')
        before = controls('studio-before-update')
        sql_names = ','.join("'" + n + "'" for n in MODULES)
        assert int(sql(TARGET, "SELECT count(*) FROM ir_module_module WHERE state='installed' AND name IN (" + sql_names + ')')) == len(MODULES)
        updated = False
        try:
            run('update-studio-owners', ['-u',','.join(MODULES)], database=TARGET, directory=DEST, roots=[PROFILE,*addon_roots(TARGET)])
            updated = True
        finally:
            assert armed == guard('verify')
            assert all_guards(TARGET) == original_guards
            assert module_census(TARGET) == baseline_census
            after = controls('studio-after-update')
            for key in ('farms','rights','directory','species','process','boms','fullread','routes'):
                assert before[key] == after[key], key
            result = {'census':baseline_census,'updated':updated,'ids':armed,'species':after['species'],
                      'process':after['process'],'full_views':sum('value_sha256' in v for v in after['fullread'].values()),
                      'core':sql(TARGET,"SELECT latest_version FROM ir_module_module WHERE name='step_agriculture_core'")}
            (DEST / 'combined-studio.json').write_text(json.dumps(result,sort_keys=True))
            print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
