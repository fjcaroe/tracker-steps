"""Registry checks for the exact finance package; call from a private Odoo shell.

This is not a deployment or an Enterprise-uninstall tool. The native reference
still contains the batch provider; Community checks only the real payment-based
format engine and balance analytics. No bank transmission is supported.
"""
import json


LEGACY_XMLIDS = {
    'step_account_treasury_batch': (
        'field_res_partner_bank__step_bancoestado_payment_method',
        'selection__res_partner_bank__step_bancoestado_payment_method__01',
        'selection__res_partner_bank__step_bancoestado_payment_method__02',
        'view_partner_bank_form_bancoestado'),
    'step_bank_security': (
        'field_res_partner_bank__step_security_credit_type',
        'selection__res_partner_bank__step_security_credit_type__1',
        'selection__res_partner_bank__step_security_credit_type__2',
        'selection__res_partner_bank__step_security_credit_type__3',
        'selection__res_partner_bank__step_security_credit_type__4',
        'selection__res_partner_bank__step_security_credit_type__5',
        'view_partner_bank_security'),
}


def metadata_snapshot(sql, database):
    """Capture BEFORE/AFTER from the new private native clone, with original IDs.

    `sql` is the validator's existing read-only query helper. Bank views retain
    their exact original architecture; only these eleven legacy XMLIDs may
    change noupdate from false to true. No business snapshot is normalized.
    """
    clauses = []
    for module, names in LEGACY_XMLIDS.items():
        clauses.append("(d.module='" + module + "' AND d.name IN (" +
                       ','.join("'" + name + "'" for name in names) + '))')
    scope = ' OR '.join(clauses)
    xmlids = sql(database, "SELECT coalesce(jsonb_agg(to_jsonb(d)-'write_date'-'write_uid' ORDER BY d.id),'[]'::jsonb) FROM ir_model_data d WHERE " + scope)
    views = sql(database, "SELECT coalesce(jsonb_agg(to_jsonb(v)-'write_date'-'write_uid' ORDER BY v.id),'[]'::jsonb) FROM ir_ui_view v WHERE v.id IN (SELECT d.res_id FROM ir_model_data d WHERE d.model='ir.ui.view' AND (" + scope + '))')
    return {'xmlids': json.loads(xmlids), 'views': json.loads(views)}


def verify_metadata(before, after):
    expected = {(module, name) for module, names in LEGACY_XMLIDS.items() for name in names}
    assert {(row['module'], row['name']) for row in before['xmlids']} == expected, 'Missing original banking XMLIDs'
    assert len(before['xmlids']) == len(after['xmlids']) == 11
    now = {row['id']: row for row in after['xmlids']}
    changed = []
    for row in before['xmlids']:
        got = now.get(row['id'])
        assert got and got == dict(row, noupdate=True), ('Banking XMLID identity changed', row['id'])
        if row['noupdate'] is False:
            changed.append(row['module'] + '.' + row['name'])
    assert len(before['views']) == len(after['views']) == 2
    assert before['views'] == after['views'], 'Original banking view metadata/architecture changed'
    return {'original_xmlids_preserved': 11, 'original_views_exact': 2,
            'only_noupdate_false_to_true': changed}


def verify(env, mode):
    assert mode in ('community', 'cerro-copy')
    versions = {'step_account_balance_analytic': '18.0.1.1.0',
                'step_bank_export_core': '18.0.1.0.0'}
    if mode == 'cerro-copy':
        versions.update({'step_account_treasury_batch': '18.0.1.5.0',
                         'step_bank_security': '18.0.1.1.0'})
    installed = env['ir.module.module'].search([('state', '=', 'installed')])
    actual = {module.name: module.latest_version for module in installed if module.name in versions}
    assert actual == versions, (actual, versions)
    from odoo.addons.step_bank_export_core.hooks import LEGACY_FIELDS, LEGACY_VIEWS, SELECTION_VALUES
    aliases = {}
    for namespace, name in LEGACY_FIELDS.items():
        name = 'field_res_partner_bank__' + name
        source, core = env.ref(namespace + '.' + name), env.ref('step_bank_export_core.' + name)
        assert source == core and core.model == 'res.partner.bank' and core.ttype == 'selection'
        aliases[namespace + '.' + name] = core.id
        field_name = core.name
        for value in SELECTION_VALUES[field_name]:
            name = 'selection__res_partner_bank__%s__%s' % (field_name, value)
            source, core_selection = env.ref(namespace + '.' + name), env.ref('step_bank_export_core.' + name)
            assert source == core_selection and core_selection.field_id == core and core_selection.value == value
            aliases[namespace + '.' + name] = core_selection.id
    for namespace, name in LEGACY_VIEWS.items():
        source, core = env.ref(namespace + '.' + name), env.ref('step_bank_export_core.' + name)
        assert source == core and core.model == 'res.partner.bank'
        aliases[namespace + '.' + name] = core.id
    form = env['res.partner.bank'].get_view(view_type='form')['arch']
    assert form.count('name="step_bancoestado_payment_method"') == 1
    assert form.count('name="step_security_credit_type"') == 1
    assert env['step.bank.export.service']._abstract
    assert not env['ir.model.access'].search([('model_id.model', '=', 'step.bank.export.service')])
    balance = env['ir.module.module'].search([('name', '=', 'step_account_balance_analytic')])
    assert balance.dependencies_id.mapped('name') == ['step_accounting_multicurrency_core']
    if mode == 'community':
        assert not installed.filtered(lambda module: module.license == 'OEEL-1')
        # Formats really run on Community payments. This is not a batch engine.
        assert 'account.batch.payment' not in env.registry
    else:
        assert 'account.batch.payment' in env.registry
        for name in ('view_batch_payment_form_treasury_review',):
            view = env.ref('step_account_treasury_batch.' + name)
            env['account.batch.payment'].get_view(view_id=view.id, view_type='form')
        env['account.batch.payment'].get_view(view_id=env.ref('step_bank_security.view_batch_security').id,
                                            view_type='form')
    result = {'mode': mode, 'versions': versions, 'aliases': aliases,
              'payment_formats_use_original_model': env['account.payment']._table == 'account_payment',
              'batch_conversion_certified': False, 'writes_to_source': False}
    print('FINANCE_FRONTIER_OK ' + json.dumps(result, sort_keys=True))
    return result
