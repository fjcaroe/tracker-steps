"""Registry checks for the exact finance package; call from a private Odoo shell.

This is not a deployment or an Enterprise-uninstall tool. The native reference
still contains the batch provider; Community checks only the real payment-based
format engine and balance analytics. No bank transmission is supported.
"""
import json


LEGACY_XMLIDS = {
    'step_account_treasury_batch': (
        'model_res_partner_bank',
        'field_account_setup_bank_manual_config__step_bancoestado_payment_method',
        'field_res_partner_bank__step_bancoestado_payment_method',
        'selection__res_partner_bank__step_bancoestado_payment_method__01',
        'selection__res_partner_bank__step_bancoestado_payment_method__02',
        'view_partner_bank_form_bancoestado'),
    'step_bank_security': (
        'model_res_partner_bank',
        'field_account_setup_bank_manual_config__step_security_credit_type',
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
    their exact original architecture; only these fifteen legacy XMLIDs may
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
    assert len(before['xmlids']) == len(after['xmlids']) == 15
    now = {row['id']: row for row in after['xmlids']}
    changed = []
    for row in before['xmlids']:
        got = now.get(row['id'])
        assert got and got == dict(row, noupdate=True), ('Banking XMLID identity changed', row['id'])
        if row['noupdate'] is False:
            changed.append(row['module'] + '.' + row['name'])
    assert len(before['views']) == len(after['views']) == 2
    current_views = {row['id']: row for row in after['views']}
    for row in before['views']:
        got = current_views.get(row['id'])
        assert got, 'Original banking view ID changed'
        # Odoo's native _inverse_arch records the new source file and keeps
        # the previous source architecture when the same XML moves modules.
        audit = {'arch_fs', 'arch_prev', 'arch_updated'}
        assert {k: v for k, v in row.items() if k not in audit} == {
            k: v for k, v in got.items() if k not in audit}, 'Original banking view architecture/permissions changed'
        assert got['arch_fs'] == 'step_bank_export_core/views/res_partner_bank_views.xml'
        assert got['arch_updated'] is False
        original_arch = row['arch_db'].get('en_US') if isinstance(row['arch_db'], dict) else row['arch_db']
        assert got['arch_prev'] in (row['arch_prev'], original_arch), 'Original banking view previous architecture changed'
    return {'original_xmlids_preserved': 15, 'original_view_ids_preserved': 2,
            'only_noupdate_false_to_true': changed,
            'view_source_file': 'step_bank_export_core/views/res_partner_bank_views.xml',
            'view_architecture_and_permissions_exact': True}


def verify(env, mode, draft_grouping=False):
    assert mode in ('community', 'cerro-copy')
    versions = {'step_account_balance_analytic': '18.0.1.1.0',
                'step_bank_export_core': '18.0.1.2.1',
                'step_accounting_multicurrency_core': '18.0.1.1.0'}
    if mode == 'cerro-copy':
        versions.update({'step_account_treasury_batch': '18.0.1.5.1',
                         'step_bank_security': '18.0.1.1.1',
                         'step_accounting_multicurrency': '18.0.2.1.0'})
    installed = env['ir.module.module'].search([('state', '=', 'installed')])
    actual = {module.name: module.latest_version for module in installed if module.name in versions}
    assert actual == versions, (actual, versions)
    from odoo.addons.step_accounting_multicurrency_core.hooks import (
        CORE as CURRENCY_CORE, LEGACY as CURRENCY_LEGACY, FIELDS as CURRENCY_FIELDS,
        MODELS as CURRENCY_MODELS, VIEWS as CURRENCY_VIEWS, owned_names as currency_names)
    currency_aliases = {}
    assert len(currency_names()) == 37 and 'model_account_report' not in currency_names()
    for model_name in CURRENCY_MODELS:
        name = 'model_' + model_name.replace('.', '_')
        model = env.ref(CURRENCY_CORE + '.' + name)
        assert model._name == 'ir.model' and model.model == model_name and model_name in env.registry
        assert model == env.ref(CURRENCY_LEGACY + '.' + name)
        currency_aliases[CURRENCY_LEGACY + '.' + name] = model.id
    for model_name, names in CURRENCY_FIELDS.items():
        assert model_name in env.registry
        for field_name in names:
            name = 'field_' + model_name.replace('.', '_') + '__' + field_name
            field = env.ref(CURRENCY_CORE + '.' + name)
            assert field._name == 'ir.model.fields' and (field.model, field.name) == (model_name, field_name)
            assert field.ttype == env[model_name]._fields[field_name].type
            assert field == env.ref(CURRENCY_LEGACY + '.' + name)
            if model_name == 'account.bank.statement.line':
                assert env[model_name]._fields['move_id'].comodel_name == 'account.move'
                assert field.related == 'move_id.' + field_name
            currency_aliases[CURRENCY_LEGACY + '.' + name] = field.id
    for name, model_name in zip(CURRENCY_VIEWS, ('account.move', 'account.move.line', 'account.payment',
                                                'account.payment.register', 'res.config.settings')):
        view = env.ref(CURRENCY_CORE + '.' + name)
        assert view._name == 'ir.ui.view' and view.model == model_name
        assert view == env.ref(CURRENCY_LEGACY + '.' + name)
        currency_aliases[CURRENCY_LEGACY + '.' + name] = view.id
    assert len(currency_aliases) == 37
    from odoo.addons.step_bank_export_core.hooks import LEGACY_FIELDS, LEGACY_VIEWS, SELECTION_VALUES, RELATED_MODEL
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
        model = env.ref(namespace + '.model_res_partner_bank')
        assert model == env.ref('step_bank_export_core.model_res_partner_bank') and model.model == 'res.partner.bank'
        aliases[namespace + '.model_res_partner_bank'] = model.id
        if RELATED_MODEL in env.registry:
            name = 'field_account_setup_bank_manual_config__' + field_name
            field = env.ref(namespace + '.' + name)
            assert field == env.ref('step_bank_export_core.' + name)
            assert field.model == RELATED_MODEL and field.related == 'res_partner_bank_id.' + field_name
            aliases[namespace + '.' + name] = field.id
    assert len(aliases) == (13 if RELATED_MODEL in env.registry else 11)
    for namespace, name in LEGACY_VIEWS.items():
        source, core = env.ref(namespace + '.' + name), env.ref('step_bank_export_core.' + name)
        assert source == core and core.model == 'res.partner.bank'
        aliases[namespace + '.' + name] = core.id
    assert len(aliases) == (15 if RELATED_MODEL in env.registry else 13)
    form = env['res.partner.bank'].get_view(view_type='form')['arch']
    assert form.count('name="step_bancoestado_payment_method"') == 1
    assert form.count('name="step_security_credit_type"') == 1
    assert env['step.bank.export.service']._abstract
    assert not env['ir.model.access'].search([('model_id.model', '=', 'step.bank.export.service')])
    wizard = env['step.bank.export.wizard']
    assert wizard._transient and wizard._fields['payment_ids'].comodel_name == 'account.payment'
    assert wizard._fields['file_data'].attachment is False
    acl = env['ir.model.access'].search([('model_id.model', '=', wizard._name)])
    assert len(acl) == 1 and acl.group_id == env.ref('account.group_account_manager')
    assert all(acl[name] for name in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink'))
    for name, domain in (('rule_bank_export_wizard_owner', "[('create_uid', '=', user.id)]"),
                         ('rule_bank_export_wizard_company', "[('company_id', 'in', company_ids)]")):
        rule = env.ref('step_bank_export_core.' + name)
        assert rule.model_id.model == wizard._name and not rule.groups and rule.active
        assert rule.domain_force == domain
        assert all(rule[field] for field in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink'))
    menu = env.ref('step_bank_export_core.menu_bank_export_wizard')
    action = env.ref('step_bank_export_core.action_bank_export_wizard')
    assert menu.groups_id == env.ref('account.group_account_manager') and menu.action == action
    assert action.res_model == wizard._name and action.binding_model_id.model == 'account.payment'
    assert action.groups_id == env.ref('account.group_account_manager')
    view = env.ref('step_bank_export_core.view_bank_export_wizard_form')
    wizard.get_view(view_id=view.id, view_type='form')
    for table in ('step_bank_export_wizard', 'step_bank_export_wizard_payment_rel'):
        # These are the only new transient containers. Fixtures must roll back
        # completely; no financial master or payment table is excluded.
        env.cr.execute('SELECT count(*) FROM ' + table)
        assert env.cr.fetchone()[0] == 0, 'Bank export fixture leaked into ' + table
    balance = env['ir.module.module'].search([('name', '=', 'step_account_balance_analytic')])
    assert balance.dependencies_id.mapped('name') == ['step_accounting_multicurrency_core']
    if mode == 'community':
        assert not installed.filtered(lambda module: module.license == 'OEEL-1')
        if draft_grouping:
            for name in ('step_batch_payment_grouping','step_batch_payment_core'):
                assert installed.filtered(lambda module:module.name==name).latest_version=='18.0.1.0.0'
            provider=env['account.batch.payment']
            assert provider._table=='account_batch_payment' and provider._original_module=='step_batch_payment_core'
            assert provider.create.__module__=='odoo.addons.step_batch_payment_core.models.batch_payment'
            assert env['account.payment']._fields['batch_payment_id'].comodel_name==provider._name
            assert 'bank.rec.widget' not in env.registry
        else:assert 'account.batch.payment' not in env.registry
    else:
        assert 'account.batch.payment' in env.registry
        for name in ('view_batch_payment_form_treasury_review',):
            view = env.ref('step_account_treasury_batch.' + name)
            env['account.batch.payment'].get_view(view_id=view.id, view_type='form')
        env['account.batch.payment'].get_view(view_id=env.ref('step_bank_security.view_batch_security').id,
                                            view_type='form')
    result = {'mode': mode, 'versions': versions, 'aliases': aliases,
              'draft_grouping_provider': bool(draft_grouping),
              'multicurrency_legacy_aliases': currency_aliases,
              'payment_formats_use_original_model': env['account.payment']._table == 'account_payment',
              'batch_conversion_certified': False, 'writes_to_source': False}
    print('FINANCE_FRONTIER_OK ' + json.dumps(result, sort_keys=True))
    return result
