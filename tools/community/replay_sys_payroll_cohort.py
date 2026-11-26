"""Run the independent SyS reference probes inside the private offline Odoo shell."""
import json
import re
import sys
from pathlib import Path


def run(env, probes, company, uid):
    assert re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', env.cr.dbname)
    assert not env['ir.module.module'].search_count([('state', '=', 'installed'), ('license', '=', 'OEEL-1')])
    env.cr.execute("""SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal
                      AND tgname='steps_sys_history_guard_row' AND tgenabled='O'""")
    assert env.cr.fetchone() == (4,)
    names = {'payroll', 'payroll_account', 'step_payroll_oca_sys_history', 'step_payroll_oca_api',
             'l10n_cl_simpledigital_payroll', 'step_hr_previred', 'step_hr_previred_simpledigital',
             'step_hr_previred_movement_dates', 'step_hr_previred_corrections'}
    modules = env['ir.module.module'].search([('state', '=', 'installed'), ('name', 'in', sorted(names))])
    assert set(modules.mapped('name')) == names
    sys.path.insert(0, str(Path(probes).resolve(strict=True)))
    import probe_sys_october_drafts
    import probe_sys_payroll_book
    import probe_sys_structure_accounting

    # Each probe owns its isolated transaction or rolls its savepoints back.
    # Keep independent results when an individual feature still fails.
    failed = []
    for name, probe in [('ownership', probe_sys_structure_accounting.probe), ('book', probe_sys_payroll_book.probe),
                        ('drafts', probe_sys_october_drafts.probe)]:
        try:
            result = probe(env, company, uid)
            print('SYS_COMMUNITY_RECEIPT', name, json.dumps(result, sort_keys=True), flush=True)
        except Exception:
            import traceback
            traceback.print_exc()
            failed.append(name)
        finally:
            env.cr.rollback()
            env.invalidate_all(flush=False)
    assert not failed, 'Uncertified SyS flows: ' + ','.join(failed)
