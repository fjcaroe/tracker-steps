"""Adopt existing field/view records without replacing SQL columns or XMLIDs.

Both XMLID namespaces reference the same records. Odoo's uninstall mechanism
retains records owned by another namespace; the Community core becomes that
owner before the optional Enterprise report bridge is upgraded or retired.
"""
from odoo.exceptions import UserError

LEGACY = 'step_accounting_multicurrency'
CORE = 'step_accounting_multicurrency_core'
MODELS = ('res.company', 'res.config.settings', 'account.move', 'account.move.line',
          'account.payment', 'account.payment.register')
FIELDS = {
    'res.company': ('operational_currency_id',),
    'res.config.settings': ('operational_currency_id',),
    'account.move': ('operational_currency_id', 'operational_rate_date', 'observed_exchange_rate',
                     'operational_debit', 'operational_credit'),
    'account.move.line': ('operational_currency_id', 'operational_exchange_rate', 'operational_debit',
                          'operational_credit', 'operational_balance', 'is_operational_exchange_adjustment'),
    'account.payment': ('operational_currency_id', 'observed_exchange_rate', 'conversion_amount', 'conversion_currency_id'),
    'account.payment.register': ('operational_currency_id', 'observed_exchange_rate', 'conversion_amount', 'conversion_currency_id'),
    # Native Community delegation through move_id, with original field IDs.
    'account.bank.statement.line': ('operational_currency_id', 'operational_rate_date', 'observed_exchange_rate',
                                    'operational_debit', 'operational_credit'),
}
VIEWS = ('view_move_form_multicurrency_steps', 'view_move_line_tree_multicurrency_steps',
         'view_account_payment_form_operational_currency', 'view_account_payment_register_operational_currency',
         'res_config_settings_view_form_operational_currency')


def owned_names():
    return set(VIEWS) | {'field_%s__%s' % (model.replace('.', '_'), name)
                        for model, names in FIELDS.items() for name in names} | {
                            'model_' + model.replace('.', '_') for model in MODELS}


def alias(env, record, namespace, noupdate):
    alias_target(env, record.name, record.model, record.res_id, namespace, noupdate)


def alias_target(env, name, model, res_id, namespace, noupdate):
    data = env['ir.model.data']
    existing = data.search([('module', '=', namespace), ('name', '=', name)])
    if existing:
        if len(existing) != 1 or (existing.model, existing.res_id) != (model, res_id):
            raise UserError('La propiedad multimoneda tiene un identificador en conflicto: %s.%s' % (namespace, name))
    else:
        data.create({'module': namespace, 'name': name, 'model': model,
                     'res_id': res_id, 'noupdate': noupdate})


def adopt_legacy_records(env):
    records = env['ir.model.data'].search([('module', '=', LEGACY), ('name', 'in', sorted(owned_names()))])
    for record in records:
        if record.model == 'ir.model.fields':
            field = env['ir.model.fields'].browse(record.res_id).exists()
            if not field or field.name not in FIELDS.get(field.model, ()):
                raise UserError('El campo multimoneda heredado no coincide con su definición: %s' % record.name)
            if field.model == 'account.bank.statement.line' and field.related != 'move_id.' + field.name:
                raise UserError('El campo multimoneda delegado perdió su relación original: %s' % record.name)
        elif record.model == 'ir.model':
            model = env['ir.model'].browse(record.res_id).exists()
            if not model or model.model not in MODELS or record.name != 'model_' + model.model.replace('.', '_'):
                raise UserError('El modelo multimoneda heredado no coincide: %s' % record.name)
        elif record.model != 'ir.ui.view' or record.name not in VIEWS:
            raise UserError('El identificador multimoneda heredado tiene un modelo inesperado: %s' % record.name)
        alias(env, record, CORE, record.noupdate)
        # Keep the old API identifier, without letting an upgrade of the report
        # bridge remove data now maintained by the Community module.
        record.noupdate = True


def preserve_legacy_xmlids(env):
    for name in MODELS:
        model = env['ir.model']._get(name)
        alias_target(env, 'model_' + name.replace('.', '_'), 'ir.model', model.id, CORE, False)
    name = 'account.bank.statement.line'
    if name not in env.registry:
        raise UserError('Falta el proveedor Community original de %s.' % name)
    for field_name in FIELDS[name]:
        field = env['ir.model.fields']._get(name, field_name)
        if not field or field.related != 'move_id.' + field_name or field_name not in env[name]._fields:
            raise UserError('Falta el campo multimoneda delegado original: %s.%s' % (name, field_name))
        alias_target(env, 'field_account_bank_statement_line__' + field_name, 'ir.model.fields', field.id, CORE, False)
    records = env['ir.model.data'].search([('module', '=', CORE), ('name', 'in', sorted(owned_names()))])
    if len(records) != len(owned_names()):
        raise UserError('La propiedad multimoneda Community está incompleta.')
    for record in records:
        alias(env, record, LEGACY, True)
