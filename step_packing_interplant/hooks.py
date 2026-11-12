from odoo import _, Command
from odoo.exceptions import ValidationError


def preserve_legacy_tag_companies(env):
    """Keep the native company of pre-existing tags when their last quant leaves."""
    tags = env['stock.quant.package'].sudo().search([
        ('is_fruit_tag', '=', True), ('company_id', '!=', False),
        ('step_packing_company_id', '=', False)])
    for tag in tags:
        company = tag.company_id
        documents = tag.step_process_reception_id.company_id | tag.step_packing_production_id.company_id
        if (any(q.company_id != company for q in tag.quant_ids)
                or any(c != company for c in documents)):
            raise ValidationError(_('Revise la compañía de origen de la tarja %s antes de actualizar.', tag.name))
        # This is an existing readonly native field, not a new company assignment.
        # Preserve IDs, receipts, masters, history and stock quantities.
        env.cr.execute('UPDATE stock_quant_package SET step_packing_company_id=%s '
                       'WHERE id=%s AND step_packing_company_id IS NULL', [company.id, tag.id])
        tag.invalidate_recordset(['step_packing_company_id'])
        # company_id already has this value. Do not force a recomputation here:
        # it would rewrite audit timestamps on historical packages.
    env.flush_all()


def configure_shipment_dispatch_types(env):
    dispatch_types = env['step.freight.dispatch.type'].with_context(active_test=False)
    named = dispatch_types.search([('name', '=ilike', 'Embarque')])
    if not named and not dispatch_types.search_count([('step_recipient_kind', '=', 'shipment')], limit=1):
        company = env.ref('base.main_company')
        named = dispatch_types.create({'name': 'Embarque', 'company_id': company.id,
            'company_ids': [Command.set(company.ids)], 'step_recipient_kind': 'shipment'})
    for dispatch_type in named.filtered(lambda record: record.active and record.step_recipient_kind in (False, 'customer', 'shipment')):
        values = {'step_recipient_kind': 'shipment'}
        company = dispatch_type.company_id
        assigned = dispatch_type.company_ids
        if assigned and assigned.root_id == company.root_id:
            same_group = env['res.company'].search([('id', 'child_of', company.root_id.id)])
            missing = same_group - assigned
            if missing:
                values['company_ids'] = [Command.link(branch.id) for branch in missing]
        if dispatch_type.step_recipient_kind != 'shipment' or 'company_ids' in values:
            dispatch_type.write(values)


def post_init_hook(env):
    preserve_legacy_tag_companies(env)
    mapping = {'Despacho a cliente': 'customer', 'Retira cliente': 'customer',
               'Despacho a productor': 'producer', 'Traslado Interplanta': 'interplant'}
    for name, kind in mapping.items():
        records = env['step.freight.dispatch.type'].search([('name', '=', name),
            ('step_recipient_kind', '=', False)])
        if records:
            # Initialize only the newly introduced classification, preserving
            # historical business values and their audit timestamps.
            env.cr.execute('UPDATE step_freight_dispatch_type SET step_recipient_kind=%s WHERE id IN %s',
                [kind, tuple(records.ids)])
            records.invalidate_recordset(['step_recipient_kind'])
    configure_shipment_dispatch_types(env)
