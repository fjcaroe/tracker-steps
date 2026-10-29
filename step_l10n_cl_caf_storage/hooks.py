"""Exact aliases only; never replace a loaded native Enterprise provider."""
from odoo.exceptions import UserError

from odoo.addons.step_l10n_cl_caf_custody_core.custody import MODEL

CORE = 'step_l10n_cl_caf_storage'


def check_provider_boundary(env):
    provider = env.registry.models.get(MODEL)
    if provider and any(base.__dict__.get('_module') == 'l10n_cl_edi' for base in provider.__mro__):
        raise UserError('CAF ya tiene proveedor cargado; usar el puente nativo de referencia, no reemplazar su clase.')
    if env['ir.module.module'].search_count([('name', '=', 'l10n_cl_edi'), ('state', '=', 'installed')]):
        raise UserError('La transición del proveedor CAF Enterprise requiere su aceptación integral independiente.')


def _alias(env, owner, name, model, record_id):
    data = env['ir.model.data']
    existing = data.search([('module', '=', owner), ('name', '=', name)])
    if existing:
        if len(existing) != 1 or (existing.model, existing.res_id) != (model, record_id):
            raise UserError('Identidad CAF en conflicto: %s.%s' % (owner, name))
    else:
        data.create({'module': owner, 'name': name, 'model': model,
                     'res_id': record_id, 'noupdate': True})


def preserve_original_aliases(env):
    model = env['ir.model']._get(MODEL)
    _alias(env, 'l10n_cl_edi', 'model_l10n_cl_dte_caf', 'ir.model', model.id)
    for name in env[MODEL]._fields:
        field = env['ir.model.fields']._get(MODEL, name)
        _alias(env, 'l10n_cl_edi', 'field_l10n_cl_dte_caf__' + name, 'ir.model.fields', field.id)
    field = env['ir.model.fields']._get('l10n_latam.document.type', 'l10n_cl_dte_caf_ids')
    _alias(env, 'l10n_cl_edi', 'field_l10n_latam_document_type__l10n_cl_dte_caf_ids', 'ir.model.fields', field.id)
    for value in ('in_use', 'spent'):
        name = 'selection__l10n_cl_dte_caf__status__' + value
        selection = env.ref(CORE + '.' + name)
        _alias(env, 'l10n_cl_edi', name, 'ir.model.fields.selection', selection.id)
    for owner, name in (('l10n_cl_edi', 'access_dte_caf_manager'), ('l10n_cl_edi_stock', 'access_dte_caf_manager')):
        own_name = 'access_caf_account_manager' if owner == 'l10n_cl_edi' else 'access_caf_stock_manager'
        _alias(env, owner, name, 'ir.model.access', env.ref(CORE + '.' + own_name).id)
    _alias(env, 'l10n_cl_edi', 'l10n_cl_dte_caf_comp_rule', 'ir.rule', env.ref(CORE + '.caf_company_rule').id)
