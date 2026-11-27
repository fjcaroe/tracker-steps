"""Qualify the expanded native Cerro upgrade and protected records against its restored source."""
import argparse
import hashlib
import json
from pathlib import Path

from check_cerro_cold_studio import histories
from check_cerro_estimation_profile import snapshot as estimate_contract
from check_cerro_packing_categories import categories
from compare_cerro_studio_strict import NATIVE, result
from restore_cerro_studio_strict import module_census, sql

SOURCE = 'MANAGEMENT_QA_CERRO_CUSTODY_20261126U40Q'
DATABASE = 'MANAGEMENT_QA_CERRO_BOM_20261126U40B'


def season_contract(database):
    return sql(database, """SELECT (SELECT md5(string_agg(to_jsonb(s)::text,chr(10) ORDER BY s.id))
                                      FROM step_temporada s),
       (SELECT md5(string_agg(to_jsonb(rel)::text,chr(10) ORDER BY rel.step_temporada_id,rel.res_company_id))
          FROM res_company_step_temporada_rel rel),
       (SELECT md5(string_agg(to_jsonb(a)::text,chr(10) ORDER BY a.id)) FROM ir_model_fields a WHERE a.id=27057),
       (SELECT md5(string_agg((to_jsonb(r)-'write_date')::text,chr(10) ORDER BY r.id)) FROM ir_rule r WHERE r.id=553)""")


def verify(trial, database):
    if trial.parent != NATIVE or not trial.name.startswith('native-catalog-graph-'):
        raise ValueError('Expected an isolated Cerro native graph trial')
    protected = json.loads((trial/'before.json').read_text())
    assert protected == json.loads((trial/'after.json').read_text())
    assert protected['guard_enabled'] and protected['changed'] == 0
    native = result(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL')
    native_directory = result(NATIVE/'native-directory-reference/result.log','CERRO_DIRECTORY')
    reference = result(NATIVE/'fullread/native.log','CERRO_FULL_READ')
    current = result(trial/'postflight.log','CERRO_DIRECTORY')
    season = result(trial/'postflight.log','CERRO_SEASON')
    assert current['directory'] == native_directory['directory'] and current['rights'] == native['rights']
    assert len(reference) == 23 and current['fullread'] == reference
    paths = current['routes']['direct_menu_routes']
    originals = native['routes']['direct_menu_routes']
    assert len(originals) == 23 and paths.keys() == originals.keys()
    for view, routes in originals.items():
        assert any(r['action'] == v['action'] and r['kind'] == v['kind'] and set(r['menus']) & set(v['menus'])
                   for r in routes for v in paths[view]), view
    rows = histories(SOURCE)
    assert histories(database) == rows
    assert season_contract(SOURCE) == season_contract(database)
    assert categories(SOURCE) == categories(database)
    assert estimate_contract(SOURCE) == estimate_contract(database)
    census = module_census(database)
    assert not census['pending']
    versions = sql(database, """SELECT name,latest_version FROM ir_module_module WHERE state='installed'
                       AND name IN ('step_agriculture_core','step_agriculture_catalogs','step_cerro_studio_farms')
                       ORDER BY name""").splitlines()
    assert len(versions) == 3
    rule_write_time_changed = sql(SOURCE,"SELECT write_date FROM ir_rule WHERE id=553") != sql(database,"SELECT write_date FROM ir_rule WHERE id=553")
    return {'identical_rows_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
            'rule_write_time_changed':rule_write_time_changed,'season':season,'views':len(reference),'original_menu_paths':len(paths),
                      'field_rule_and_seasons_sha256':hashlib.sha256(season_contract(SOURCE).encode()).hexdigest(),
                      'identity_guard':protected,'census':census,'versions':versions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial', type=Path, required=True)
    args = parser.parse_args()
    trial = args.trial.resolve()
    database = 'MANAGEMENT_QA_CERRO_BOM_20261126U42N' if trial.name == 'native-catalog-graph-u42n' else DATABASE
    print(json.dumps(verify(trial,database),sort_keys=True))


if __name__ == '__main__':
    main()
