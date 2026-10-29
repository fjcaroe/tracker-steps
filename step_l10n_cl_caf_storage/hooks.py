"""Exact aliases only; never replace a loaded native Enterprise provider."""
from odoo.exceptions import UserError

from odoo.addons.step_l10n_cl_caf_custody_core.custody import MODEL

CORE = 'step_l10n_cl_caf_storage'


def reject_pending_native_provider(cr):
    cr.execute("SELECT name FROM ir_module_module WHERE name IN (%s,%s) "
               "AND state IN ('installed','to install','to upgrade','to remove') LIMIT 1",
               ['l10n_cl_edi', 'step_l10n_cl_caf_native_reference'])
    if cr.fetchone():
        raise UserError('El proveedor CAF nativo está instalado o participa en la misma transición; no mezclar proveedores.')


def check_model_registration(pool, cr):
    """Before _build_model: reject overwrite, same-graph EE and cold tables."""
    if MODEL in pool:
        raise UserError('CAF ya tiene una clase registrada; no se reemplaza ningún proveedor existente.')
    reject_pending_native_provider(cr)
    cr.execute('SELECT to_regclass(%s)', ['public.l10n_cl_dte_caf'])
    if not cr.fetchone()[0]:
        return
    # A cold table must never be interpreted as an empty clean installation.
    # Only a prior installation of this exact provider can load its own table;
    # original native tables need a separately accepted identity transition.
    cr.execute("SELECT d.res_id FROM ir_model_data d JOIN ir_model m ON m.id=d.res_id "
               "JOIN ir_module_module p ON p.name=d.module WHERE d.model='ir.model' "
               "AND d.module=%s AND d.name='model_l10n_cl_dte_caf' AND m.model=%s "
               "AND p.state IN ('installed','to upgrade')", [CORE, MODEL])
    owners = cr.fetchall()
    if len(owners) != 1:
        raise UserError('Existe una tabla CAF fría sin propiedad Community comprobada; se requiere adopción explícita.')


def check_provider_boundary(env):
    reject_pending_native_provider(env.cr)
    provider = env.registry.models.get(MODEL)
    if provider and provider._original_module != CORE:
        raise UserError('CAF ya tiene proveedor cargado; usar el puente nativo de referencia, no reemplazar su clase.')


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
