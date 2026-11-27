from odoo.exceptions import ValidationError

from .models import DTE_STATES


OWNER = 'step_cerro_picking_list_history'
ORIGINALS = {
    'l10n_cl_edi_stock': ('l10n_cl_dte_status', 'l10n_latam_document_number'),
    'quality_control': ('quality_check_todo',),
    'step_packing_ticket_revision': ('step_external_reception_folio', 'step_reception_product_ids',
        'step_reception_packaging_ids', 'step_reception_container_qty', 'step_reception_net_kg', 'step_reception_avg_kg'),
}


def bindings():
    for module, names in ORIGINALS.items():
        for name in names:
            yield module, 'field_stock_picking__'+name, 'ir.model.fields'
    for code, _label in DTE_STATES:
        yield 'l10n_cl_edi_stock', 'selection__stock_picking__l10n_cl_dte_status__'+code, 'ir.model.fields.selection'


def adopt_history(env):
    if env['ir.module.module'].search_count([('name','in',list(ORIGINALS)), ('state','in',['installed','to install','to upgrade'])]):
        raise ValidationError('Las consultas históricas de Cerro requieren el perfil Community de recepciones.')
    aliases = []
    for module, name, model in bindings():
        record = env.ref(module+'.'+name)
        previous = env.ref(OWNER+'.'+name, raise_if_not_found=False)
        if record._name != model or (previous and previous != record):
            raise ValidationError('Cambió la identidad histórica de '+name)
        aliases.append(dict(xml_id=OWNER+'.'+name, record=record, noupdate=True))
    env['ir.model.data']._update_xmlids(aliases)


def verify_history(env):
    for module, name, _model in bindings():
        if env.ref(OWNER+'.'+name) != env.ref(module+'.'+name):
            raise ValidationError('La referencia histórica no se conservó: '+name)
