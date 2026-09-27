"""Export shipment, fruit-tag traceability and dispatch documents (T35)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ExportShipment(models.Model):
    _inherit = "step.export.export"

    stage_id = fields.Many2one(default=lambda self: self.env.ref("step_export.export_stage_instruction").id)
    state = fields.Selection([
        ("draft", "Instructivo"), ("validated", "Validado"),
        ("dispatched", "Despachado"), ("shipped", "Embarcado"),
        ("invoiced", "Facturado"), ("settled", "Liquidado"),
    ], default="draft", required=True, copy=False, tracking=True)
    shipment_number = fields.Char(string="Núm. embarque", readonly=True, copy=False, index=True)
    transport_type = fields.Selection([
        ("sea", "Marítimo"), ("air", "Aéreo"), ("land", "Terrestre"),
    ], string="Tipo de embarque", required=True, default="sea")
    sales_program_id = fields.Many2one("step.export.sales.program", string="Programa de ventas")
    season_id = fields.Many2one("step.temporada", string="Temporada")
    species_id = fields.Many2one("step.especie", string="Especie")
    receiver_id = fields.Many2one("res.partner", string="Recibidor")
    consignee_id = fields.Many2one("res.partner", string="Consignatario")
    notify_id = fields.Many2one("res.partner", string="Notify")
    freight_forwarder_id = fields.Many2one("res.partner", string="Agente de carga")
    customs_agent_id = fields.Many2one("res.partner", string="Agente de aduana")
    carrier_id = fields.Many2one("res.partner", string="Naviera o aerolínea")
    vessel_id = fields.Many2one("step.export.vessel", string="Nave")
    sale_mode_id = fields.Many2one("step.export.sale.mode", string="Modalidad")
    incoterm_id = fields.Many2one("account.incoterms", string="Incoterm")
    destination_country_id = fields.Many2one("res.country", string="País destino")
    origin_port = fields.Char(string="POL / AOL")
    destination_port = fields.Char(string="POD / AOD")
    departure_date = fields.Date(string="Fecha zarpe")
    arrival_date = fields.Date(string="Fecha llegada")
    dus_folio = fields.Char(string="DUS")
    bl_folio = fields.Char(string="BL / AWB")
    ivv_folio = fields.Char(string="IVV")
    line_ids = fields.One2many("step.export.shipment.line", "shipment_id", string="Carga")
    tag_ids = fields.Many2many("stock.quant.package", string="Tarjas", domain="[('is_fruit_tag', '=', True)]")
    dispatch_guide_ids = fields.Many2many("step.dispatch.guide", string="Guías SII")
    packing_list_ids = fields.One2many("step.export.packing.list", "shipment_id", string="Packing Lists")
    picking_ids = fields.Many2many("stock.picking", string="Despachos de inventario")
    sale_order_ids = fields.One2many("sale.order", "step_export_shipment_id", string="Notas de venta")
    invoice_ids = fields.One2many("account.move", "step_export_shipment_id", string="Facturas")
    settlement_id = fields.Many2one("step.export.receiver.settlement", string="Liquidación recibidor", readonly=True, copy=False)
    claim_ids = fields.Many2many("step.export.customer.claim", string="Reclamos")
    box_qty = fields.Float(compute="_compute_load", store=True)
    kg_qty = fields.Float(compute="_compute_load", store=True)

    _sql_constraints = [
        ("shipment_number_company_unique", "unique(company_id, shipment_number)",
         "El número de embarque ya existe en esta empresa."),
    ]

    def write(self, vals):
        locked = {"sales_program_id", "receiver_id", "season_id", "species_id",
                  "transport_type", "line_ids", "tag_ids", "dispatch_guide_ids",
                  "company_id"}
        if locked.intersection(vals) and any(record.state in ("shipped", "invoiced", "settled") for record in self):
            raise UserError(_("La carga y el programa de un embarque ya embarcado no pueden modificarse."))
        stage_xmlid = {
            "draft": "export_stage_instruction", "validated": "export_stage_instruction",
            "dispatched": "export_stage_dispatched", "shipped": "export_stage_shipped",
            "invoiced": "export_stage_invoiced", "settled": "export_stage_settled",
        }
        if "state" in vals and "stage_id" not in vals:
            vals["stage_id"] = self.env.ref("step_export.%s" % stage_xmlid[vals["state"]]).id
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("shipment_number"):
                transport = vals.get("transport_type") or "sea"
                vals["shipment_number"] = self.env["ir.sequence"].next_by_code(
                    "step.export.shipment.%s" % transport) or "Nuevo"
        return super().create(vals_list)

    @api.depends("line_ids.box_qty", "line_ids.kg_qty")
    def _compute_load(self):
        for record in self:
            record.box_qty = sum(record.line_ids.mapped("box_qty"))
            record.kg_qty = sum(record.line_ids.mapped("kg_qty"))

    def action_validate_shipment(self):
        for record in self:
            if record.state != "draft" or not record.sales_program_id or not record.line_ids:
                raise UserError(_("Indique programa y carga antes de validar el instructivo."))
            if record.sales_program_id.state != "current":
                raise UserError(_("El programa de ventas debe estar vigente."))
            if record.receiver_id and record.receiver_id != record.sales_program_id.partner_id:
                raise ValidationError(_("El recibidor debe coincidir con el programa."))
            record.write({"state": "validated", "receiver_id": record.sales_program_id.partner_id.id,
                          "season_id": record.sales_program_id.season_id.id,
                          "species_id": record.sales_program_id.species_id.id})
        return True

    def action_dispatch(self):
        for record in self:
            if record.state != "validated" or not record.dispatch_guide_ids:
                raise UserError(_("Valide el instructivo y registre al menos una guía de despacho."))
            if any(guide.state != "confirmed" for guide in record.dispatch_guide_ids):
                raise UserError(_("Todas las guías deben estar confirmadas."))
            record._check_tag_load()
            record.state = "dispatched"
        return True

    def action_ship(self):
        for record in self:
            if record.state != "dispatched" or not record.dus_folio or not record.bl_folio:
                raise UserError(_("Registre DUS y BL/AWB del embarque despachado."))
            record.state = "shipped"
        return True

    def action_invoice(self):
        for record in self:
            if record.state != "shipped" or not record.invoice_ids.filtered(lambda move: move.state == "posted"):
                raise UserError(_("Registre y publique la factura de exportación antes de facturar."))
            record.state = "invoiced"
        return True

    def _check_tag_load(self):
        for record in self:
            if not record.tag_ids:
                raise ValidationError(_("Asocie las tarjas reales del embarque."))
            if any(not tag.is_fruit_tag for tag in record.tag_ids):
                raise ValidationError(_("La carga solo admite tarjas de fruta."))
            others = self.search([("id", "!=", record.id),
                                  ("state", "not in", ["draft", "validated"]),
                                  ("tag_ids", "in", record.tag_ids.ids)])
            if others:
                raise ValidationError(_("Una tarja ya pertenece a otro embarque despachado."))


class ExportShipmentLine(models.Model):
    _name = "step.export.shipment.line"
    _description = "Resumen de carga de embarque"

    shipment_id = fields.Many2one("step.export.export", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True)
    packaging_id = fields.Many2one("product.packaging", string="Embalaje")
    package_type_id = fields.Many2one("stock.package.type", string="Tipo pallet")
    variety_id = fields.Many2one("step.variedad", string="Variedad")
    category_id = fields.Many2one("step.management.fruit.category", string="Categoría")
    caliber_id = fields.Many2one("step.management.fruit.caliber", string="Calibre")
    label = fields.Char(string="Etiqueta")
    pallet_qty = fields.Float(string="Pallets", required=True)
    boxes_per_pallet = fields.Float(string="Cajas por pallet", required=True)
    kg_per_box = fields.Float(string="Kg por caja", required=True)
    box_qty = fields.Float(string="Cajas", compute="_compute_quantities", store=True)
    kg_qty = fields.Float(string="Kilos", compute="_compute_quantities", store=True)

    @api.depends("pallet_qty", "boxes_per_pallet", "kg_per_box")
    def _compute_quantities(self):
        for record in self:
            record.box_qty = record.pallet_qty * record.boxes_per_pallet
            record.kg_qty = record.box_qty * record.kg_per_box

    @api.constrains("pallet_qty", "boxes_per_pallet", "kg_per_box")
    def _check_quantities(self):
        for record in self:
            if min(record.pallet_qty, record.boxes_per_pallet, record.kg_per_box) <= 0:
                raise ValidationError(_("Pallets, cajas por pallet y kg por caja deben ser positivos."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.export.export"].browse([
            vals["shipment_id"] for vals in vals_list if vals.get("shipment_id")])
        if any(parent.state in ("shipped", "invoiced", "settled") for parent in parents):
            raise UserError(_("No agregue carga a un embarque ya embarcado."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(line.shipment_id.state in ("shipped", "invoiced", "settled") for line in self):
            raise UserError(_("No modifique la carga de un embarque ya embarcado."))
        return super().write(vals)

    def unlink(self):
        if any(line.shipment_id.state in ("shipped", "invoiced", "settled") for line in self):
            raise UserError(_("No elimine carga de un embarque ya embarcado."))
        return super().unlink()


class ExportPackingList(models.Model):
    _name = "step.export.packing.list"
    _description = "Packing List de exportación"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="Nuevo", required=True, copy=False, readonly=True)
    shipment_id = fields.Many2one("step.export.export", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="shipment_id.company_id", store=True)
    guide_id = fields.Many2one("step.dispatch.guide", string="Guía de despacho", required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    container_number = fields.Char(string="Container number")
    seal_number = fields.Char(string="Seal number")
    tag_ids = fields.Many2many("stock.quant.package", string="Tarjas")
    box_qty = fields.Integer(compute="_compute_totals")
    kg_qty = fields.Float(compute="_compute_totals")

    _sql_constraints = [
        ("packing_guide_unique", "unique(guide_id)", "La guía ya tiene Packing List."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("step.export.packing.list") or "Nuevo"
        return super().create(vals_list)

    @api.depends("tag_ids.box_count", "tag_ids.kilos_total")
    def _compute_totals(self):
        for record in self:
            record.box_qty = sum(record.tag_ids.mapped("box_count"))
            record.kg_qty = sum(record.tag_ids.mapped("kilos_total"))

    @api.constrains("shipment_id", "guide_id", "tag_ids")
    def _check_links(self):
        for record in self:
            if record.guide_id not in record.shipment_id.dispatch_guide_ids:
                raise ValidationError(_("La guía debe pertenecer al embarque."))
            if record.tag_ids - record.shipment_id.tag_ids:
                raise ValidationError(_("Las tarjas del Packing List deben pertenecer al embarque."))

    def action_print(self):
        self.ensure_one()
        return self.env.ref("step_export.action_report_export_packing_list").report_action(self)


class ExportSaleOrder(models.Model):
    _inherit = "sale.order"

    step_export_sales_program_id = fields.Many2one("step.export.sales.program", string="Programa de ventas")
    step_export_shipment_id = fields.Many2one("step.export.export", string="Embarque")

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.step_export_shipment_id:
            vals["step_export_shipment_id"] = self.step_export_shipment_id.id
        return vals


class ExportAccountMove(models.Model):
    _inherit = "account.move"

    step_export_shipment_id = fields.Many2one("step.export.export", string="Embarque")


class ExportFruitTag(models.Model):
    _inherit = "stock.quant.package"

    step_export_shipment_ids = fields.Many2many("step.export.export", string="Embarques")
    step_export_claim_ids = fields.Many2many("step.export.customer.claim", string="Reclamos exportación")
    step_export_settlement_ids = fields.Many2many("step.export.receiver.settlement", string="Liquidaciones recibidor")
