"""Registry checks for the exact finance package; call from a private Odoo shell.

This is not a deployment or an Enterprise-uninstall tool. The native reference
still contains the batch provider; Community checks only the real payment-based
format engine and balance analytics. No bank transmission is supported.
"""
import json


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
