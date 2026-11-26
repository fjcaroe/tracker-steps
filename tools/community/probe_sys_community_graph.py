"""Use the official Odoo module graph to test the SyS private startup closure.

Run with the pinned Community runtime on PYTHONPATH and a private overlay.
The report distinguishes absent source names, unresolved dependencies and
replacement candidates. This command never changes installed module states.
"""
import argparse
import json
from pathlib import Path
import re


def main():
    import odoo
    from odoo.modules import module
    from odoo.modules.graph import Graph
    from odoo.tools import config

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True)
    p.add_argument('--odoo-config', required=True)
    p.add_argument('--addons-path', required=True)
    p.add_argument('--data-dir', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not re.fullmatch(r'COMMUNITY_SYS_PREVIRED_ADMISSION_[A-Z0-9_]{1,30}', args.database):
        raise ValueError('A private SyS admission derivative is required.')
    config.parse_config(['-c', args.odoo_config, '-d', args.database,
                         '--db-filter=^' + args.database + '$', '--db_host=/var/run/postgresql',
                         '--addons-path=' + args.addons_path, '--data-dir=' + args.data_dir,
                         '--max-cron-threads=0', '--workers=0', '--no-http', '--load=base,web'])
    module.initialize_sys_path()
    candidates = {'payroll', 'payroll_account', 'step_payroll_contracts', 'step_payroll_oca_api',
                  'step_simpledigital_oca_base', 'step_simpledigital_oca_security',
                  'step_payroll_oca_sys_history'}
    with odoo.sql_db.db_connect(args.database).cursor() as cr:
        cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cr.execute('SELECT current_database(), current_setting(\'transaction_read_only\')')
        if cr.fetchone() != (args.database, 'on'):
            raise ValueError('A read-only private connection is required.')
        cr.execute("SELECT name,license FROM ir_module_module WHERE state='installed'")
        installed = dict(cr.fetchall())
        if not {'hr_payroll', 'step_hr_previred', 'l10n_cl_simpledigital_payroll'} <= installed.keys():
            raise ValueError('SyS source payroll graph missing.')
        native = Graph()
        native.add_modules(cr, sorted(installed))
        proposed = Graph()
        proposed.add_modules(cr, sorted(installed.keys() | candidates))
        names = set(proposed.keys())
        licenses = {n: (module.get_manifest(n) or {}).get('license') for n in names}
        if any(v not in ('LGPL-3', 'AGPL-3', 'GPL-3', 'GPL-2', 'GPL-2 or any later version',
                         'GPL-3 or any later version') for v in licenses.values()):
            raise ValueError('Unreviewed license in the candidate module graph.')
        missing = {}
        for name in sorted(installed.keys() - names):
            manifest = module.get_manifest(name)
            missing[name] = {'native_license': installed[name], 'manifest_found': bool(manifest),
                             'unresolved_dependencies': sorted(set(manifest['depends']) - names)
                             if manifest else []}
        cr.execute("SELECT count(*) FROM ir_module_module WHERE state LIKE 'to %'")
        if cr.fetchone()[0]:
            raise ValueError('Pending module operation in private restore.')
        result = dict(database=args.database, installed=len(installed), native_state_resolved=len(native),
                      candidate_graph_resolved=len(proposed), native_oeel=sum(v == 'OEEL-1' for v in installed.values()),
                      missing_installed=missing, candidate_engine_resolved=sorted(candidates & names),
                      candidate_engine_missing=sorted(candidates - names),
                      resolved_dependencies={name: sorted(proposed[name].info['depends']) for name in sorted(names)},
                      previred_graph={n: n in names for n in sorted(installed) if 'previred' in n or
                                      n == 'l10n_cl_simpledigital_payroll'},
                      full_source_graph_resolved=not missing and candidates <= names,
                      module_states_changed=False, registry_started=False)
    with args.output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
