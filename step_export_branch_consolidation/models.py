from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from odoo.tools.safe_eval import safe_eval


def branch_companies(env, company):
    # Existing user memberships only; current company stays first for defaults.
    if company not in env.user.company_ids:
        raise AccessError(_('La compañía actual no está autorizada al usuario.'))
    permitted = env.user.company_ids.filtered(lambda row: row.root_id == company.root_id)
    return company | (permitted - company)


def check_sources(document, sources):
    for source in sources:
        source.check_access('read')
        if source.company_id and (source.company_id.root_id != document.company_id.root_id or
                                  source.company_id not in document.env.companies):
            raise ValidationError(_('Seleccione documentos de sucursales autorizadas de la misma empresa.'))


class ExportActions(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        result = super()._get_action_dict()
        aliases = ('step_export.action_export_shipping_instructions',
                   'step_export.action_export_packing_list', 'step_export.action_export_consult_tags')
        if self.id in [self.env.ref(alias).id for alias in aliases]:
            previous = result.get('context') or {}
            context = safe_eval(previous, dict(self.env.context, uid=self.env.uid)) if isinstance(previous,str) else dict(previous)
            companies = branch_companies(self.env, self.env.company)
            context.update(allowed_company_ids=companies.ids, step_export_branch_scope=True)
            result['context'] = context
        return result


class Shipment(models.Model):
    _inherit = 'step.export.export'

    step_branch_company_ids = fields.Many2many('res.company', compute='_compute_branch_companies')

    @api.depends('company_id')
    @api.depends_context('uid')
    def _compute_branch_companies(self):
        for shipment in self:
            shipment.step_branch_company_ids = branch_companies(self.env, shipment.company_id)

    @api.constrains('company_id', 'tag_ids', 'dispatch_guide_ids')
    def _check_branch_sources(self):
        for shipment in self:
            check_sources(shipment, shipment.tag_ids)
            check_sources(shipment, shipment.dispatch_guide_ids)


class Guide(models.Model):
    _inherit = 'step.dispatch.guide'

    def _inverse_export_shipment(self):
        for guide in self:
            target = guide.step_export_shipment_id
            previous = self.env['step.export.export'].search([('dispatch_guide_ids','in',guide.ids)])
            if target:
                check_sources(target,guide)
            if previous - target:
                if self.env['step.export.packing.list'].search([('guide_id','=',guide.id)]):
                    raise ValidationError(_('La guía tiene un Packing List; no cambie su embarque.'))
                (previous-target).write({'dispatch_guide_ids':[(3,guide.id)]})
            if target and target not in previous:
                target.write({'dispatch_guide_ids':[(4,guide.id)]})


class Package(models.Model):
    _inherit = 'stock.quant.package'

    @api.constrains('step_export_shipment_ids','step_guide_ids','step_invoice_ids',
                    'step_dus_shipment_ids','step_bl_shipment_ids','company_id')
    def _check_document_links(self):
        for tag in self:
            company = tag.company_id or self.env.company
            shipments = tag.step_export_shipment_ids
            for document in shipments | tag.step_dus_shipment_ids | tag.step_bl_shipment_ids:
                document.check_access('read')
                if document.company_id.root_id != company.root_id or document.company_id not in self.env.companies:
                    raise ValidationError(_('Los embarques deben pertenecer a sucursales autorizadas de la misma empresa.'))
            for guide in tag.step_guide_ids:
                guide.check_access('read')
                if guide.company_id.root_id != company.root_id or guide.company_id not in self.env.companies:
                    raise ValidationError(_('La guía debe pertenecer a una sucursal autorizada de la misma empresa.'))
            # Accounting documents keep their original exact-company boundary.
            if any(invoice.company_id != company for invoice in tag.step_invoice_ids):
                raise ValidationError(_('La factura debe pertenecer a la misma compañía de la tarja.'))
            if tag.step_dus_shipment_ids - shipments or tag.step_bl_shipment_ids - shipments:
                raise ValidationError(_('Seleccione DUS y BL/AWB de los embarques vinculados a la tarja.'))
            if any(not row.dus_folio for row in tag.step_dus_shipment_ids) or any(not row.bl_folio for row in tag.step_bl_shipment_ids):
                raise ValidationError(_('El embarque seleccionado debe tener su DUS o BL/AWB registrado.'))
            if shipments and (tag.step_guide_ids - shipments.dispatch_guide_ids or tag.step_invoice_ids - shipments.invoice_ids):
                raise ValidationError(_('Seleccione guías y facturas de los embarques vinculados a la tarja.'))

    @api.onchange('step_export_shipment_ids')
    def _onchange_document_shipments(self):
        super()._onchange_document_shipments()
        for tag in self:
            company = tag.company_id or self.env.company
            tag.step_invoice_ids = tag.step_invoice_ids.filtered(lambda invoice: invoice.company_id == company)
