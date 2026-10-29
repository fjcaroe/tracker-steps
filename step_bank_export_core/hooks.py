"""Adopt the existing columns and field IDs before either batch adapter upgrades."""
from odoo.exceptions import UserError

CORE = 'step_bank_export_core'
RELATED_MODEL = 'account.setup.bank.manual.config'
LEGACY_FIELDS = {
    'step_account_treasury_batch': 'step_bancoestado_payment_method',
    'step_bank_security': 'step_security_credit_type',
}
LEGACY_VIEWS = {
    'step_account_treasury_batch': 'view_partner_bank_form_bancoestado',
    'step_bank_security': 'view_partner_bank_security',
}
SELECTION_VALUES = {
    'step_bancoestado_payment_method': ('01', '02'),
    'step_security_credit_type': ('1', '2', '3', '4', '5'),
}


def _alias(env, namespace, name, record, noupdate):
    data = env['ir.model.data']
    existing = data.search([('module', '=', namespace), ('name', '=', name)])
    if existing:
        if len(existing) != 1 or existing.model != record._name or existing.res_id != record.id:
            raise UserError('Identificador bancario en conflicto: %s.%s' % (namespace, name))
    else:
        data.create({'module': namespace, 'name': name, 'model': record._name,
                     'res_id': record.id, 'noupdate': noupdate})
    # This is Odoo's loader API for retaining an existing XMLID during the
    # current upgrade. Do not turn the persisted original flag into a lease.
    if data._load_xmlid(namespace + '.' + name) != record:
        raise UserError('El identificador bancario cargado no coincide: %s.%s' % (namespace, name))


def adopt_legacy_fields(env):
    for namespace, field_name in LEGACY_FIELDS.items():
        name = 'field_res_partner_bank__' + field_name
        legacy = env['ir.model.data'].search([('module', '=', namespace), ('name', '=', name)])
        if not legacy:
            continue
        field = env['ir.model.fields'].browse(legacy.res_id).exists()
        if len(legacy) != 1 or legacy.model != 'ir.model.fields' or not field or (
                field.model, field.name, field.ttype) != ('res.partner.bank', field_name, 'selection'):
            raise UserError('El campo bancario heredado no coincide: %s.%s' % (namespace, name))
        _alias(env, CORE, name, field, legacy.noupdate)
        env['ir.model.data']._load_xmlid(namespace + '.' + name)
        for value in SELECTION_VALUES[field_name]:
            selection_name = 'selection__res_partner_bank__%s__%s' % (field_name, value)
            selection_data = env['ir.model.data'].search([
                ('module', '=', namespace), ('name', '=', selection_name)])
            if not selection_data:
                continue
            selection = env['ir.model.fields.selection'].browse(selection_data.res_id).exists()
            if len(selection_data) != 1 or selection_data.model != 'ir.model.fields.selection' or not selection or (
                    selection.field_id != field or selection.value != value):
                raise UserError('La selección bancaria heredada no coincide: %s.%s' % (namespace, selection_name))
            _alias(env, CORE, selection_name, selection, selection_data.noupdate)
            env['ir.model.data']._load_xmlid(namespace + '.' + selection_name)
    for namespace, field_name in LEGACY_FIELDS.items():
        name = 'model_res_partner_bank'
        legacy = env['ir.model.data'].search([('module', '=', namespace), ('name', '=', name)])
        if legacy:
            model = env['ir.model'].browse(legacy.res_id).exists()
            if len(legacy) != 1 or legacy.model != 'ir.model' or not model or model.model != 'res.partner.bank':
                raise UserError('El modelo bancario heredado no coincide: %s.%s' % (namespace, name))
            _alias(env, CORE, name, model, legacy.noupdate)
            env['ir.model.data']._load_xmlid(namespace + '.' + name)
        name = 'field_account_setup_bank_manual_config__' + field_name
        legacy = env['ir.model.data'].search([('module', '=', namespace), ('name', '=', name)])
        if legacy:
            field = env['ir.model.fields'].browse(legacy.res_id).exists()
            if len(legacy) != 1 or legacy.model != 'ir.model.fields' or not field or (
                    field.model, field.name, field.ttype, field.related) != (
                    RELATED_MODEL, field_name, 'selection', 'res_partner_bank_id.' + field_name):
                raise UserError('El campo bancario relacionado heredado no coincide: %s.%s' % (namespace, name))
            if RELATED_MODEL not in env.registry:
                raise UserError('Falta el proveedor original de %s; no se puede retirar su campo bancario.' % RELATED_MODEL)
            _alias(env, CORE, name, field, legacy.noupdate)
            env['ir.model.data']._load_xmlid(namespace + '.' + name)
    for namespace, name in LEGACY_VIEWS.items():
        legacy = env['ir.model.data'].search([('module', '=', namespace), ('name', '=', name)])
        if not legacy:
            continue
        view = env['ir.ui.view'].browse(legacy.res_id).exists()
        if len(legacy) != 1 or legacy.model != 'ir.ui.view' or not view or (
                view.model != 'res.partner.bank' or view.inherit_id != env.ref('base.view_partner_bank_form')):
            raise UserError('La vista bancaria heredada no coincide: %s.%s' % (namespace, name))
        _alias(env, CORE, name, view, legacy.noupdate)
        env['ir.model.data']._load_xmlid(namespace + '.' + name)


def preserve_legacy_xmlids(env):
    for namespace, field_name in LEGACY_FIELDS.items():
        name = 'field_res_partner_bank__' + field_name
        field = env.ref(CORE + '.' + name)
        if field._name != 'ir.model.fields' or (field.model, field.name, field.ttype) != (
                'res.partner.bank', field_name, 'selection') or field_name not in env['res.partner.bank']._fields:
            raise UserError('La propiedad bancaria Community no coincide: %s' % name)
        _alias(env, namespace, name, field, True)
        for value in SELECTION_VALUES[field_name]:
            selection_name = 'selection__res_partner_bank__%s__%s' % (field_name, value)
            selection = env.ref(CORE + '.' + selection_name)
            if selection._name != 'ir.model.fields.selection' or selection.field_id != field or selection.value != value:
                raise UserError('La selección bancaria Community no coincide: %s' % selection_name)
            _alias(env, namespace, selection_name, selection, True)
        bank_model = env['ir.model']._get('res.partner.bank')
        _alias(env, CORE, 'model_res_partner_bank', bank_model, False)
        _alias(env, namespace, 'model_res_partner_bank', bank_model, True)
        if RELATED_MODEL in env.registry:
            if field_name not in env[RELATED_MODEL]._fields:
                raise UserError('Falta el campo bancario del proveedor original: %s.%s' % (RELATED_MODEL, field_name))
            related = env['ir.model.fields']._get(RELATED_MODEL, field_name)
            name = 'field_account_setup_bank_manual_config__' + field_name
            _alias(env, CORE, name, related, False)
            _alias(env, namespace, name, related, True)
    for namespace, name in LEGACY_VIEWS.items():
        view = env.ref(CORE + '.' + name)
        if view._name != 'ir.ui.view' or view.model != 'res.partner.bank' or view.inherit_id != env.ref('base.view_partner_bank_form'):
            raise UserError('La vista bancaria Community no coincide: %s' % name)
        _alias(env, namespace, name, view, True)
