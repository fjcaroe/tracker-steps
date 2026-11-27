"""Run in a private Odoo shell, then compare the two receipts offline."""
import argparse
import json
from pathlib import Path


COMPANIES = (2, 5, 6, 7, 8, 12, 13, 29, 32, 36, 37)
NATIVE = 'MANAGEMENT_QA_SYS_PREVIRED_20261126U40N'
COMMUNITY = 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L'


def capture(env):
    from odoo.modules.module import get_manifest
    from probe_sys_batch_form import probe as form
    from probe_sys_batch_payment_archive import probe as archive
    from probe_sys_october_batch import probe as batch

    database = env.cr.dbname
    if not __debug__ or database not in (NATIVE, COMMUNITY):
        raise ValueError('Use the designated isolated restores with normal Python.')
    candidate = database == COMMUNITY
    modules = env['ir.module.module'].search([('state', '=', 'installed')])
    if candidate:
        name = 'step_payroll_oca_sys_history'
        assert len(modules) == 190 and not modules.filtered(lambda m: m.license == 'OEEL-1')
        assert modules.filtered(lambda m: m.name == name).latest_version == get_manifest(name)['version'] == '18.0.1.6.0'
    else:
        assert modules.filtered(lambda m: m.name == 'hr_payroll' and m.license == 'OEEL-1')
    receipt = {'database': database, 'forms': {}, 'installed': len(modules)}

    def run(fn, *args, **kwargs):
        try:
            item = fn(env, *args, **kwargs)
            if item.get('error'):
                raise ValueError('Batch verification failed at %s (%s)' % (item.get('attempted'), item['error']))
            return item
        finally:
            env.cr.rollback()
            env.invalidate_all(flush=False)

    for company in COMPANIES:
        receipt['forms'][str(company)] = run(form, company, 2)
    receipt['batch_archive'] = run(archive, 2)
    receipt['individual_archive'] = run(archive, 2, individual=True)
    receipt['july'] = run(batch, 2, 2, followup=True, payment_reference=True, individual_payment=True, member_actions=True)
    receipt['standalone'] = run(batch, 2, 2, payment_reference=True, standalone=True)
    receipt['october'] = run(batch, 37, 2, followup=True, reopen=not candidate, frozen_reopen=candidate)
    return receipt


def verify(native, community):
    if not __debug__ or native['database'] != NATIVE or community['database'] != COMMUNITY:
        raise ValueError('Use genuine native and cold Community receipts.')
    for name in ('forms', 'batch_archive', 'individual_archive', 'standalone'):
        assert native[name] == community[name], name
    assert set(community['forms']) == set(map(str, COMPANIES))
    assert community['standalone']['bytes'] > 0
    left, right = dict(native['july']), dict(community['july'])
    source, generated = (dict(item.pop('action_payment_report')) for item in (left, right))
    assert left == right, 'July workflow or individual file differs'
    assert source.pop('member_reports_match_batch') == [True] * 6
    assert generated.pop('member_reports_match_batch') == [False] * 6
    assert source.pop('member_reports_only_own_row') == [False] * 6
    assert generated.pop('member_reports_only_own_row') == [True] * 6
    assert source == generated and generated['rows'] == 6
    left, right = dict(native['october']), dict(community['october'])
    assert right.pop('protected_frozen_slips') == 5
    before, frozen = left.pop('recomputed'), right.pop('recomputed')
    assert before['slips'] == {'verify': 5} and frozen['slips'] == {'draft': 5}
    assert left == right, 'October workflow or reopened accounting entries differ'
    assert right['reclosed']['reused_moves'] == right['reclosed']['previous_still_present'] == 5
    return {'forms': len(community['forms']), 'july_batch_csv_rows': generated['rows'],
            'individual_csv_files_scoped_to_employee': 6, 'reopened_moves_reused': 5}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--community', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.native.read_bytes()), json.loads(args.community.read_bytes()))))
