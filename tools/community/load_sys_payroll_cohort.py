"""Call the pinned official CLI for a private, guarded SyS payroll installation.

The two recalculation-producing supplier seed aliases are deliberately absent
from the free supplier overlay. Keep their original SyS records through the
official module cleanup. All other cleanup remains subject to SQL identity
and history guards.
"""
import argparse
import functools
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys

from preflight_original_history_storage import require
from sys_previred_preservation import identifier


ROOTS = ('step_payroll_contracts', 'step_payroll_oca_api', 'step_simpledigital_oca_base',
         'step_simpledigital_oca_security', 'step_payroll_oca_sys_history')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True)
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--runtime', required=True, type=Path)
    p.add_argument('--config', required=True)
    p.add_argument('--addons-path', required=True)
    p.add_argument('--data-dir', required=True)
    p.add_argument('--logfile', required=True)
    args = p.parse_args()
    database = args.database
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', database),
            'sys-cohort-private-loader-required')
    plan = json.loads(args.plan.read_bytes())
    require(plan['database'] == database and plan['integral_conversion'] is False,
            'sys-cohort-scoped-plan-required')
    aliases = plan['retained_supplier_aliases']
    require({(x['name'], x['model']) for x in aliases} == {
        ('structure_chile', 'hr.payroll.structure'), ('structure_type_chile', 'hr.payroll.structure.type')
    } and len(aliases) == 2, 'sys-cohort-unexpected-retention-aliases')
    model_file = args.runtime.resolve() / 'odoo/addons/base/models/ir_model.py'
    require(hashlib.sha256(model_file.read_bytes()).hexdigest() ==
            '43bfd1ebb04688fdb8013f2e941a4c9f39f69a9b4e8ab0d406683908e2ae5b6e',
            'sys-cohort-unreviewed-official-cleanup')
    sys.path.insert(0, str(args.runtime.resolve()))
    from odoo.addons.base.models.ir_model import IrModelData
    from odoo import cli

    original = IrModelData._process_end
    require(Path(inspect.getsourcefile(original)).resolve() == model_file,
            'sys-cohort-unexpected-cleanup-method')
    calls = []

    @functools.wraps(original)
    def process_end(self, modules):
        cr = self.env.cr
        require(cr.dbname == database, 'sys-cohort-cleanup-scope')
        cr.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O' "
                   "AND tgname='steps_sys_history_guard_row'")
        require(cr.fetchone() == (4,), 'sys-cohort-closed-history-guards-required')
        cr.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O' "
                   "AND tgname='steps_sys_identity_row'")
        require(cr.fetchone()[0] == len(plan['protected']), 'sys-cohort-metadata-guards-required')
        cr.execute("SELECT count(*) FROM ir_module_module WHERE state='to remove' OR (state IN "
                   "('installed','to install','to upgrade') AND (license='OEEL-1' OR name IN "
                   "('hr_payroll','hr_payroll_account')))")
        require(cr.fetchone() == (0,), 'sys-cohort-cleanup-enterprise-runtime')
        for alias in aliases:
            cr.execute("SELECT id,res_id,model,noupdate FROM ir_model_data WHERE "
                       "module='l10n_cl_simpledigital_payroll' AND name=%s", (alias['name'],))
            require(cr.fetchall() == [(alias['xml_pk'], alias['res_id'], alias['model'], False)],
                    'sys-cohort-supplier-identity-drift')
            model = self.env[alias['model']]
            require(model._auto and not model._transient and model._table == alias['model'].replace('.', '_'),
                    'sys-cohort-original-master-model-required')
            selected = ','.join(identifier(k) for k in alias['columns'])
            cr.execute('SELECT md5(to_jsonb(t)::text) FROM (SELECT ' + selected + ' FROM public.'
                       + identifier(model._table) + ' WHERE id=%s) t', (alias['res_id'],))
            require(cr.fetchone() == (alias['original_md5'],), 'sys-cohort-supplier-master-drift')
        self.env.registry.loaded_xmlids.update('l10n_cl_simpledigital_payroll.' + a['name'] for a in aliases)
        result = original(self, modules)
        calls.append(sorted(modules))
        return result

    IrModelData._process_end = process_end
    try:
        sys.argv = [str(args.runtime / 'odoo-bin'), '-c', args.config, '-d', database,
                    '--db-filter=^' + database + '$', '--db_host=/var/run/postgresql',
                    '--data-dir=' + args.data_dir, '--addons-path=' + args.addons_path,
                    '--load=base,web', '--workers=0', '--max-cron-threads=0', '--no-http',
                    '--stop-after-init', '--without-demo=all', '--logfile=' + args.logfile,
                    '-u', ','.join(ROOTS)]
        try:
            cli.main()
        except SystemExit as exc:
            if exc.code not in (0, None):
                raise
        require(calls, 'sys-cohort-official-cleanup-not-exercised')
        print('SYS_OFFICIAL_CLEANUP ' + json.dumps(calls))
    finally:
        IrModelData._process_end = original


if __name__ == '__main__':
    main()
