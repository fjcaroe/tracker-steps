"""Executed in Odoo shell; archive legacy data then request a real uninstall.

Never compute or pay a payslip. The runner supplies EXPECTED_DATABASE and the
trusted engine stage. All originals are retained in protected JSON snapshots.
"""
import json
import re
from psycopg2 import sql

assert env.cr.dbname == EXPECTED_DATABASE
legacy = env['ir.module.module'].search([('name', '=', 'l10n_cl_hr'), ('state', '=', 'installed')])
if legacy:
    # Follow installed dependents transitively; do not touch native hr_payroll.
    retiring = legacy
    while True:
        deps = env['ir.module.module'].search([('state', '=', 'installed'), ('dependencies_id.name', 'in', retiring.mapped('name'))])
        newer = retiring | deps
        if newer == retiring:
            break
        retiring = newer
    assert set(retiring.mapped('name')) <= {
        'l10n_cl_hr', 'l10n_cl_hr_account_analytic', 'l10n_cl_hr_electronic_book',
        'l10n_cl_hr_payroll_account', 'l10n_cl_hr_payroll_extended_14',
        'step_hr_contract_lifecycle_agriculture', 'step_hr_previred_blueminds',
    }, 'Unexpected legacy dependent: ' + ','.join(retiring.mapped('name'))
    owned = env['ir.model.data'].search([('module', 'in', retiring.mapped('name'))])
    native = {'hr.employee', 'hr.contract', 'hr.payslip', 'hr.payslip.line',
              'hr.payslip.worked_days', 'hr.payslip.input', 'hr.salary.rule',
              'hr.salary.rule.category', 'hr.payroll.structure', 'hr.payroll.structure.type'}
    model_names = native | set(owned.filtered(lambda r: r.model == 'ir.model').mapped('res_id') and
                             env['ir.model'].browse(owned.filtered(lambda r: r.model == 'ir.model').mapped('res_id')).mapped('model'))
    archived = 0
    for name in sorted(model_names):
        if name not in env.registry.models:
            continue
        model = env[name]
        if model._transient or not model._auto or not re.fullmatch('[a-z0-9_]+', model._table):
            continue
        env.cr.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t ORDER BY id').format(sql.Identifier(model._table)))
        for (payload,) in env.cr.fetchall():
            vals = {'source_model': name, 'source_id': payload['id'], 'company_id': payload.get('company_id'), 'payload': payload}
            prior = env['step.payroll.legacy.snapshot'].sudo().search([('source_model', '=', name), ('source_id', '=', payload['id'])])
            if prior:
                assert prior.payload == payload, 'Archive conflict: ' + name
            else:
                env['step.payroll.legacy.snapshot'].sudo().create(vals)
                archived += 1
    # Ownership transfer keeps structures/rules and financial references alive.
    # UI, access rules, fields and old engine models are genuinely uninstalled.
    keep = owned.filtered(lambda r: r.model in native or r.model in {
        'hr.work.entry.type', 'hr.leave.type', 'hr.contract.type', 'resource.calendar',
        'resource.calendar.attendance', 'res.partner', 'account.journal', 'step.previred.profile',
    })
    structures = env['hr.payroll.structure'].browse(keep.filtered(lambda r: r.model == 'hr.payroll.structure').mapped('res_id')).exists()
    structures.write({'step_legacy_payroll': True})
    contracts = env['hr.contract'].with_context(active_test=False).search([])
    contracts.write({'step_payroll_migration_review': True})
    for record in keep:
        record.write({'module': 'step_payroll_legacy_archive', 'name': record.module + '__' + record.name, 'noupdate': True})
    profiles = env['step.previred.profile'].with_context(active_test=False).search([('engine', '=', 'l10n_cl_hr')]) if 'step.previred.profile' in env else []
    if profiles:
        profiles.write({'active': False})
    env.cr.commit()
    print('PAYROLL_ARCHIVE_OK ' + json.dumps({'records': archived, 'retiring': retiring.mapped('name')}), flush=True)
    retiring.button_immediate_uninstall()
    print('PAYROLL_LEGACY_UNINSTALLED', flush=True)
else:
    print('PAYROLL_NO_LEGACY_ENGINE', flush=True)
