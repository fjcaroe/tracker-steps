"""Compare the strict Community screens and farm permissions with the native restored Cerro user."""
import json
from pathlib import Path

from restore_cerro_studio_strict import ROOT

NATIVE = Path('/opt/steps-validation/community-cerro-studio-catalogue-20261126U40B')
FARM = 'odoo_studio_step_fun_05371f67-0dae-476d-8fe8-d7eb8da9926f'


def result(path, prefix):
    matches = [json.loads(line[len(prefix) + 1:]) for line in path.read_text().splitlines()
               if line.startswith(prefix + ' ')]
    if len(matches) != 1:
        raise ValueError(f'Expected one receipt for {prefix} in {path.name}')
    return matches[0]


def compare():
    native = result(NATIVE / 'upgrade-final-v2/native-postflight.log', 'CERRO_FULL')
    full_native = result(NATIVE / 'fullread/native.log', 'CERRO_FULL_READ')
    farm = result(ROOT / 'fundos.log', 'CERRO_STRICT_FARMS')
    views = result(ROOT / 'views.log', 'CERRO_STRICT_VIEWS')
    assert len(full_native) == len(views['fullread']) == 23
    assert farm['farm'] == native['farm']
    assert farm['rights'] == native['rights']
    assert farm['view']['read_existing_record'] and farm['view']['visible_menu_actions']
    assert farm['aliases']['same_target_preserved'] and farm['aliases']['conflict_rejected']
    assert farm['aliases']['stale_source_removed']
    assert views['routes']['uid'] == native['routes']['uid'] == 6
    exact = {name for name in full_native if 'value_sha256' in full_native[name]
             and full_native[name] == views['fullread'][name]}
    assert FARM in exact
    routes = {k for k, v in views['routes']['direct_menu_routes'].items() if v}
    native_routes = native['routes']['direct_menu_routes']
    shared = {k for k in routes if any(edge in native_routes[k] for edge in views['routes']['direct_menu_routes'][k])}
    assert len(native_routes) == 23
    return {'farm_access': farm['rights'], 'farm_definitions': farm['farm'],
            'directory': farm['directory'], 'all_native_views': 23,
            'complete_record_equals_native': sorted(exact),
            'reached_by_original_menu': sorted(shared),
            'other_views': {name: views['fullread'][name].get('error', 'different value or layout')
                            for name in sorted(full_native.keys() - exact)}}


if __name__ == '__main__':
    print(json.dumps(compare(), sort_keys=True))
