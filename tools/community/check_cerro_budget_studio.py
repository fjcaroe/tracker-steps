"""Install the full Cerro budget graph under the original identity and category guards."""
import fcntl
import json
from pathlib import Path
import subprocess

from check_cerro_estimation_profile import BRIDGE, PROFILE as ESTIMATES, snapshot as estimates
from check_cerro_packing_categories import PACKING, PRODUCER_LINK, categories
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from restore_cerro_studio_strict import ESTIMATE_ROOT, ESTIMATE_TARGET, SOURCE, module_census

OPERATIONS = ROOT / 'harvest-source-aliases-1723e91df3cd'
HASHES = {
    'step_cosecha': '478e6ca27ff381436bee0e1bd408d984ab326822c18e75caf5b65499f86315d3',
    'step_operations_core': '10e0011f6efb638b44148d05e7c38eb336789504f955daad2b72b26cb9065afd',
    'step_labor_operations_core': '66538d420a64af8adb8c6955e29745445e92c37207f55054693030f3891f2ef4',
}


def guard(mode):
    source = Path(__file__).with_name('guard_cerro_studio_upgrade.py')
    return json.loads(subprocess.check_output([
        'runuser', '-u', 'postgres', '--', '/usr/bin/python3.10', str(source),
        '--database', ESTIMATE_TARGET, '--mode', mode], text=True))


def main():
    profile = {p.name: tree_sha(p) for p in OPERATIONS.iterdir() if p.is_dir()}
    if profile != HASHES:
        raise ValueError('The operational sources differ from the admitted providers')
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        assert (ESTIMATE_ROOT / 'packing-studio.log').is_file()
        assert not any(module_census(ESTIMATE_TARGET)[key] for key in ('pending','non_free','enterprise'))
        native_categories, native_estimates = categories(SOURCE), estimates(SOURCE)
        assert (categories(ESTIMATE_TARGET), estimates(ESTIMATE_TARGET)) == (native_categories, native_estimates)
        ids = guard('arm')
        options = dict(database=ESTIMATE_TARGET, directory=ESTIMATE_ROOT,
                       roots=[OPERATIONS, PRODUCER_LINK, PACKING, ESTIMATES, BRIDGE, *addon_roots(ESTIMATE_TARGET)])
        try:
            run('install-budgets', ['-i','step_cerro_studio_budgets'], **options)
        finally:
            assert guard('verify') == ids
            assert (categories(ESTIMATE_TARGET), estimates(ESTIMATE_TARGET)) == (native_categories, native_estimates)
        census = module_census(ESTIMATE_TARGET)
        assert not any(census[key] for key in ('pending','non_free','enterprise'))
        code = 'import json,sys\nsys.path.insert(0,' + repr(str(ROOT/'tools')) + ')\n'
        code += """from probe_cerro_studio_fullread import capture as fullread
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as client
from probe_cerro_legacy_aliases import capture as aliases
print('BUDGET_STUDIO',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env),aliases=aliases(env)),sort_keys=True))
env.cr.rollback()
"""
        run('budget-studio', [], code, **options)
        log = (ESTIMATE_ROOT/'budget-studio.log').read_text().splitlines()
        assert sum(line.startswith('BUDGET_STUDIO ') for line in log) == 1
        print(json.dumps(dict(ids=ids,census=census),sort_keys=True))


if __name__ == '__main__':
    main()
