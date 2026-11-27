"""Load the original plot estimator on a separate strict restored Cerro database."""
import fcntl
import json

from check_cerro_studio_strict import addon_roots, run, tree_sha
from restore_cerro_studio_strict import ESTIMATE_ROOT, ESTIMATE_TARGET, ROOT, SOURCE, clone_and_copy, module_census, sql

PROFILE = ROOT / 'estimate-profile-v1'
HASHES = {
    'step_management_estimation_entry': '6906abea2e17b180cea8b79167e311e30f7ec417b6218040452cfd8ad935bc0e',
    'step_management_costs': 'be3a491c9c7dbb66dcf000266ec10bc304ac979cf252700b83bce7da288e18e9',
}


def snapshot(database):
    fields = sql(database, """SELECT id,name,relation,on_delete FROM ir_model_fields
        WHERE model='step.management.estimation.line' AND name='cuartel_id'""")
    if fields != '31444|cuartel_id|step.cuartel.line|restrict':
        raise ValueError('The restored plot field is different')
    unique = sql(database, """SELECT pg_get_constraintdef(oid),convalidated FROM pg_constraint
                 WHERE conrelid='step_management_estimation_line'::regclass
                   AND conname='step_management_estimation_line_estimation_line_center_unique'""")
    if unique != 'UNIQUE (estimation_id, center_id, cuartel_id)|t':
        raise ValueError('The original plot uniqueness is missing')
    values = sql(database, """SELECT count(*),md5(string_agg(to_jsonb(t)::text,chr(10) ORDER BY id))
                 FROM step_management_estimation_line t""")
    indexes = sql(database, """SELECT indexdef FROM pg_indexes WHERE schemaname='public'
                  AND indexname='estimation_center_without_plot_uniq'""")
    return {'unique': unique, 'plot_field': fields, 'lines': values, 'partial_index': indexes}


def main():
    if {p.name: tree_sha(p) for p in PROFILE.iterdir() if p.is_dir()} != HASHES:
        raise ValueError('The admitted estimate profile changed')
    with open('/run/lock/steps-environments.lock', 'rb') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        clone_and_copy(ESTIMATE_TARGET, ESTIMATE_ROOT)
        reference = snapshot(SOURCE)
        assert snapshot(ESTIMATE_TARGET) == reference
        before = module_census(ESTIMATE_TARGET)
        assert not any(before[k] for k in ('enterprise', 'non_free', 'pending'))
        result = {}
        parameters = dict(database=ESTIMATE_TARGET, directory=ESTIMATE_ROOT, roots=[PROFILE, *addon_roots()])
        try:
            run('install-estimator', ['-i', 'step_management_estimation_entry'], **parameters)
            state = sql(ESTIMATE_TARGET, """SELECT state FROM ir_module_module
                WHERE name='step_management_estimation_entry'""")
            if state != 'installed':
                raise ValueError('The original estimator could not be installed')
            body = """import json
actor=env['res.users'].browse(6)
model=env['step.management.estimation.line'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids)
records=model.search([],order='id')
assert not model.env.su and records
for row in records:
    row.check_access('read')
    if row.cuartel_id:
        assert row.cuartel_id.centro_id==row.center_id
print('CERRO_ESTIMATE_PROFILE',json.dumps({'uid':actor.id,'visible_lines':len(records),'visible_plots':len(records.cuartel_id)}))
env.cr.rollback()
"""
            run('estimate-user', [], body, **parameters)
            if not any(l.startswith('CERRO_ESTIMATE_PROFILE ') for l in (ESTIMATE_ROOT / 'estimate-user.log').read_text().splitlines()):
                raise ValueError('The original user did not read the estimates')
            result['installed_estimator'] = True
        finally:
            after = module_census(ESTIMATE_TARGET)
            assert not any(after[k] for k in ('enterprise', 'non_free', 'pending'))
            assert snapshot(ESTIMATE_TARGET) == reference
            result.update({'source': SOURCE, 'target': ESTIMATE_TARGET, 'state': after, 'original': reference})
            (ESTIMATE_ROOT / 'estimate-result.json').write_text(json.dumps(result, sort_keys=True))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
