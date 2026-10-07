"""Tarja de fruta sobre el paquete de stock, sin duplicar el inventario."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    step_tag_kind = fields.Selection([
        ("C", "Cosecha"), ("E", "Exportación"), ("N", "Nacional"),
    ], string="Tipo de tarja", index=True)
    step_tag_state = fields.Selection([
        ("created", "Creada"), ("validated", "Validada"),
        ("processed", "Procesada"), ("repalletized", "Repaletizada"),
        ("dispatched", "Despachada / embarcada"),
        ("liquidated", "Liquidada"), ("void", "Nula"),
    ], string="Estado de tarja", default="created", index=True)
    step_producer_id = fields.Many2one("res.partner", string="Productor de origen", index=True)
    step_producer_code = fields.Char(related="step_producer_id.ref", string="Código productor", store=True)
    step_sdp_code = fields.Char(related="fundo_id.sdp_code", string="Código SDP", store=True)
    step_shipment = fields.Char(string="Embarque")
    harvest_date = fields.Date('Fecha de cosecha')
    received_at = fields.Datetime('Recepción registrada', readonly=True, copy=False)
    step_dispatch_guide = fields.Char(string="Guía SII")
    step_dus = fields.Char(string="DUS")
    step_invoice = fields.Char(string="Factura")
    step_bl_awb = fields.Char(string="BL / AWB")
    step_document_company_id = fields.Many2one('res.company', compute='_compute_document_company')
    step_guide_ids = fields.Many2many('step.dispatch.guide', string='Guía SII', check_company=True)
    step_invoice_ids = fields.Many2many('account.move', string='Factura', check_company=True,
                                      domain="[('move_type','in',['out_invoice','out_refund'])]")
    step_dus_shipment_ids = fields.Many2many('step.export.export', relation='step_tag_dus_shipment_rel',
                                            string='DUS', check_company=True)
    step_bl_shipment_ids = fields.Many2many('step.export.export', relation='step_tag_bl_shipment_rel',
                                           string='BL / AWB', check_company=True)

    @api.depends('company_id')
    @api.depends_context('company')
    def _compute_document_company(self):
        for tag in self:
            # Native packages acquire company_id from their first real quant.
            tag.step_document_company_id = tag.company_id or self.env.company

    @api.onchange('step_export_shipment_ids')
    def _onchange_document_shipments(self):
        for tag in self:
            shipments = tag.step_export_shipment_ids
            tag.step_guide_ids = shipments.dispatch_guide_ids
            tag.step_invoice_ids = shipments.invoice_ids
            tag.step_dus_shipment_ids = shipments.filtered('dus_folio')
            tag.step_bl_shipment_ids = shipments.filtered('bl_folio')

    @api.constrains('step_export_shipment_ids', 'step_guide_ids', 'step_invoice_ids',
                    'step_dus_shipment_ids', 'step_bl_shipment_ids', 'company_id')
    def _check_document_links(self):
        for tag in self:
            shipments = tag.step_export_shipment_ids
            company = tag.company_id or self.env.company
            documents = [*shipments, *tag.step_guide_ids, *tag.step_invoice_ids,
                         *tag.step_dus_shipment_ids, *tag.step_bl_shipment_ids]
            if any(record.company_id != company for record in documents):
                raise ValidationError(_('Los documentos y embarques deben pertenecer a la empresa de la tarja.'))
            if tag.step_dus_shipment_ids - shipments or tag.step_bl_shipment_ids - shipments:
                raise ValidationError(_('Seleccione DUS y BL/AWB de los embarques vinculados a la tarja.'))
            if any(not row.dus_folio for row in tag.step_dus_shipment_ids) or any(not row.bl_folio for row in tag.step_bl_shipment_ids):
                raise ValidationError(_('El embarque seleccionado debe tener su DUS o BL/AWB registrado.'))
            if shipments:
                if tag.step_guide_ids - shipments.dispatch_guide_ids or tag.step_invoice_ids - shipments.invoice_ids:
                    raise ValidationError(_('Seleccione guías y facturas de los embarques vinculados a la tarja.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_document_commands(vals)
        tags = super().create(vals_list)
        if any(shipment.state in ('shipped', 'invoiced', 'settled') for shipment in tags.step_export_shipment_ids):
            raise UserError(_('La carga de un embarque ya embarcado no puede modificarse desde una tarja.'))
        return tags

    def _check_document_commands(self, vals):
        for name in ('step_export_shipment_ids', 'step_guide_ids', 'step_invoice_ids', 'step_dus_shipment_ids', 'step_bl_shipment_ids'):
            if any(command[0] not in (3, 4, 5, 6) for command in vals.get(name, [])):
                raise UserError(_('Seleccione documentos existentes; no se modifican documentos desde la tarja.'))
    step_tag_line_ids = fields.One2many("step.fruit.package.line", "package_id", string="Detalle por productor")
    step_actual_kg = fields.Float(string="Kilos reales", compute="_compute_step_actual_kg", digits="Stock Weight")
    step_composition = fields.Selection([
        ("simple", "Simple"), ("mixed", "Mixta"),
    ], compute="_compute_step_tag_attributes", string="Composición")
    step_filling = fields.Selection([
        ("complete", "Completa"), ("partial", "Parcial"),
    ], compute="_compute_step_tag_attributes", string="Llenado")

    @api.depends("step_tag_line_ids.producer_id", "box_count", "package_type_id")
    def _compute_step_tag_attributes(self):
        for package in self:
            producers = set(package.step_tag_line_ids.mapped("producer_id").ids)
            package.step_composition = "mixed" if len(producers) > 1 else "simple"
            capacity = package.package_type_id.step_export_boxes_per_pallet
            package.step_filling = "complete" if capacity and package.box_count >= capacity else "partial"

    @api.depends("step_tag_line_ids.kilos")
    def _compute_step_actual_kg(self):
        for package in self:
            package.step_actual_kg = sum(package.step_tag_line_ids.mapped("kilos"))

    @api.onchange("fundo_id")
    def _onchange_step_producer(self):
        for package in self:
            if package.fundo_id.partner_id:
                package.step_producer_id = package.fundo_id.partner_id

    @api.constrains("step_tag_kind", "step_tag_state", "step_tag_line_ids", "step_producer_id")
    def _check_step_tag(self):
        for package in self.filtered("is_fruit_tag"):
            if not package.step_tag_kind:
                raise ValidationError(_("Seleccione el tipo C, E o N de la tarja."))
            if package.step_tag_state == "processed" and package.step_tag_kind != "C":
                raise ValidationError(_("Solo las tarjas de cosecha pueden quedar procesadas."))
            if package.step_tag_state == "liquidated" and package.step_tag_kind != "E":
                raise ValidationError(_("Solo las tarjas de exportación pueden liquidarse."))
            if package.step_tag_state not in ("created", "void"):
                lines = package.step_tag_line_ids
                if not lines or not all(line.producer_id for line in lines):
                    raise ValidationError(_("Una tarja validada requiere detalle por productor."))
                if len(set(lines.mapped("producer_id").ids)) == 1 and package.step_producer_id != lines[0].producer_id:
                    raise ValidationError(_("El productor de origen debe coincidir con el detalle de una tarja simple."))
                if package.quant_ids and not set(lines.mapped("product_id").ids).issubset(set(package.quant_ids.mapped("product_id").ids)):
                    raise ValidationError(_("Los productos del detalle no coinciden con el contenido del paquete."))

    def action_step_validate_tag(self):
        for package in self:
            if not package.is_fruit_tag or package.step_tag_state != "created":
                raise UserError(_("Solo puede validar una tarja de fruta creada."))
            package.step_tag_state = "validated"
        return True

    def write(self, vals):
        self._check_document_commands(vals)
        if 'step_export_shipment_ids' in vals:
            closed = self.step_export_shipment_ids.filtered(lambda row: row.state in ('shipped', 'invoiced', 'settled'))
            ids = {command[1] for command in vals['step_export_shipment_ids'] if command[0] == 4}
            for command in vals['step_export_shipment_ids']:
                if command[0] == 6:
                    ids.update(command[2])
            closed |= self.env['step.export.export'].browse(list(ids)).filtered(lambda row: row.state in ('shipped', 'invoiced', 'settled'))
            if closed:
                raise UserError(_('La carga de un embarque ya embarcado no puede modificarse desde una tarja.'))
        locked = {"step_tag_kind", "step_producer_id", "fundo_id", "box_count", "step_tag_line_ids",
                  "harvest_date", "received_at", "especie_id", "variedad_id", "fruit_type",
                  "fruit_category_id", "fruit_caliber_id", "step_packing_result"}
        if locked.intersection(vals) and any(
                package.is_fruit_tag and package.step_tag_state not in ("created", "void")
                for package in self):
            raise UserError(_("Una tarja validada no se modifica; cree una tarja de repaletizaje."))
        return super().write(vals)


class StepFruitPackageLine(models.Model):
    _name = "step.fruit.package.line"
    _description = "Contenido de tarja por productor"
    _order = "id"

    package_id = fields.Many2one("stock.quant.package", required=True, ondelete="cascade", index=True)
    producer_id = fields.Many2one("res.partner", string="Productor", required=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    quantity = fields.Float(string="Cantidad", digits="Product Unit of Measure", required=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", related="product_id.uom_id", store=True)
    kilos = fields.Float(string="Kilos", digits="Stock Weight", required=True)
    boxes = fields.Float(string="Cajas", digits="Product Unit of Measure")

    _sql_constraints = [
        ("positive_quantity", "check(quantity > 0 AND kilos > 0)", "Cantidad y kilos deben ser mayores a cero."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        packages = self.env["stock.quant.package"].browse([
            vals["package_id"] for vals in vals_list if vals.get("package_id")])
        if any(package.step_tag_state not in ("created", "void") for package in packages):
            raise UserError(_("No agregue detalle a una tarja validada."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(line.package_id.step_tag_state not in ("created", "void") for line in self):
            raise UserError(_("No modifique el detalle de una tarja validada."))
        return super().write(vals)

    def unlink(self):
        if any(line.package_id.step_tag_state not in ("created", "void") for line in self):
            raise UserError(_("No borre el detalle de una tarja validada."))
        return super().unlink()
