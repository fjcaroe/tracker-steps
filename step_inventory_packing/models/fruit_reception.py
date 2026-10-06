"""Datos de pesaje y tarjas en la recepción nativa de Inventario."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = "stock.picking"

    step_fruit_reception_kind = fields.Selection([
        ("process", "Fruta a proceso"), ("packed", "Fruta embalada"),
    ], string="Tipo de recepción de fruta", index=True)
    step_fruit_weighing_method = fields.Selection([
        ("manual", "Manual"), ("scale", "Balanza"),
    ], string="Registro de pesaje", default="manual")
    step_fruit_weighing_by = fields.Selection([
        ("truck", "Por camión"), ("unit", "Por unidad de traslado"),
    ], string="Tipo de pesaje", default="truck")
    step_scale_profile_id = fields.Many2one("step.scale.profile", string="Perfil de balanza")
    step_scale_capture = fields.Char(string="Captura de balanza", compute="_compute_step_scale_capture")
    step_scale_protocol = fields.Selection(related="step_scale_profile_id.protocol")
    step_scale_service_uuid = fields.Char(related="step_scale_profile_id.service_uuid")
    step_scale_characteristic_uuid = fields.Char(related="step_scale_profile_id.characteristic_uuid")
    step_scale_serial_service_uuid = fields.Char(related="step_scale_profile_id.serial_service_uuid")
    step_scale_baud_rate = fields.Integer(related="step_scale_profile_id.baud_rate")
    step_scale_weight_pattern = fields.Char(related="step_scale_profile_id.weight_pattern")
    step_scale_kg_factor = fields.Float(related="step_scale_profile_id.kg_factor")
    step_scale_read_at = fields.Datetime(string="Última lectura de balanza", readonly=True, copy=False)
    step_scale_read_raw = fields.Char(string="Trama de última lectura", readonly=True, copy=False)

    def _compute_step_scale_capture(self):
        for picking in self:
            picking.step_scale_capture = False

    @api.constrains("step_scale_profile_id", "company_id")
    def _check_scale_company(self):
        for picking in self:
            if picking.step_scale_profile_id and picking.step_scale_profile_id.company_id != picking.company_id:
                raise ValidationError(_("El perfil de balanza pertenece a otra empresa."))
    step_fruit_guide_date = fields.Date(string="Fecha guía productor")
    step_fruit_driver_id = fields.Many2one("res.partner", string="Chofer")
    step_fruit_driver_vat = fields.Char(related="step_fruit_driver_id.vat", string="RUT chofer")
    step_fruit_cost_center = fields.Char(string="Centro de costo / cuartel")
    step_fruit_gross_kg = fields.Float(string="Peso bruto kg", digits="Stock Weight")
    step_fruit_truck_tare_kg = fields.Float(string="Destare camión kg", digits="Stock Weight")
    step_fruit_container_tare_kg = fields.Float(string="Destare envases kg", digits="Stock Weight")
    step_fruit_transfer_tare_kg = fields.Float(string="Destare unidades traslado kg", digits="Stock Weight")
    step_fruit_net_kg = fields.Float(
        string="Peso neto fruta kg", compute="_compute_step_fruit_net_kg", digits="Stock Weight")

    @api.depends("step_fruit_gross_kg", "step_fruit_truck_tare_kg",
                 "step_fruit_container_tare_kg", "step_fruit_transfer_tare_kg")
    def _compute_step_fruit_net_kg(self):
        for picking in self:
            picking.step_fruit_net_kg = max(0.0, picking.step_fruit_gross_kg -
                picking.step_fruit_truck_tare_kg - picking.step_fruit_container_tare_kg -
                picking.step_fruit_transfer_tare_kg)

    @api.constrains("step_fruit_reception_kind", "picking_type_id")
    def _check_step_fruit_kind(self):
        for picking in self:
            if picking.step_fruit_reception_kind and picking.picking_type_code != "incoming":
                raise ValidationError(_("Las recepciones de fruta deben ser operaciones de entrada."))
            if picking.step_fruit_reception_kind and not picking.company_id.step_fruit_inventory_enabled:
                raise ValidationError(_("Habilite las recepciones agrícolas en la configuración de Inventario."))

    def _check_step_fruit_reception(self):
        for picking in self.filtered("step_fruit_reception_kind"):
            if not picking.fruit_fundo_id or not picking.fruit_species_id:
                raise ValidationError(_("Indique fundo y especie en la recepción de fruta."))
            if not picking.fruit_tag_line_ids:
                raise ValidationError(_("Registre las tarjas recibidas."))
            if picking.step_fruit_weighing_by == "truck":
                if picking.step_fruit_gross_kg <= 0:
                    raise ValidationError(_("Ingrese el peso bruto del camión."))
                if picking.step_fruit_net_kg <= 0:
                    raise ValidationError(_("El peso neto debe ser mayor a cero."))
                kilos = sum(picking.fruit_tag_line_ids.mapped("kilos"))
                if float_compare(kilos, picking.step_fruit_net_kg, precision_digits=2):
                    raise ValidationError(_("Los kilos de las tarjas no coinciden con el peso neto de la recepción."))
            for line in picking.fruit_tag_line_ids:
                if not line.package_id or line.package_id.name != line.tag_number:
                    raise ValidationError(_("Cada línea debe referir un paquete de stock con el mismo número de tarja."))
                expected = "C" if picking.step_fruit_reception_kind == "process" else "E"
                if line.package_id.step_tag_kind != expected:
                    raise ValidationError(_("El tipo de tarja no coincide con el tipo de recepción."))
                if line.package_id not in picking.move_line_ids.mapped("result_package_id"):
                    raise ValidationError(_("Asigne cada tarja al paquete resultante en las operaciones de stock."))

    def button_validate(self):
        self._check_step_fruit_reception()
        for picking in self.filtered(lambda row: row.step_fruit_reception_kind == 'process' and row.state != 'done'):
            producer = picking.fruit_fundo_id.partner_id
            if not producer:
                raise ValidationError(_("El fundo debe identificar al propietario de la fruta a proceso."))
            # Raw fruit remains the producer's property; it is bought only as export output.
            if any(line.owner_id and line.owner_id != producer for line in picking.move_line_ids):
                raise ValidationError(_("El propietario de la materia prima debe coincidir con el productor."))
            picking.move_line_ids.write({'owner_id': producer.id})
        result = super().button_validate()
        for picking in self.filtered(lambda record: record.step_fruit_reception_kind and record.state == "done"):
            producer = picking.fruit_fundo_id.partner_id
            if not producer:
                raise ValidationError(_("El fundo de la recepción debe tener un productor."))
            for line in picking.fruit_tag_line_ids:
                package = line.package_id
                if package.step_tag_state == "created":
                    package.write({
                        "fundo_id": picking.fruit_fundo_id.id,
                        "step_export_season_id": picking.fruit_season_id.id,
                        "especie_id": picking.fruit_species_id.id,
                        "variedad_id": picking.fruit_variety_id.id,
                        "received_at": fields.Datetime.now(),
                    })
                if not package.step_tag_line_ids:
                    products = package.quant_ids.mapped("product_id")
                    product = line.product_id or (products if len(products) == 1 else False)
                    quants = package.quant_ids.filtered(lambda quant: quant.product_id == product)
                    quantity = sum(quants.mapped("quantity"))
                    if not product or quantity <= 0:
                        raise ValidationError(_("La tarja debe contener un único producto en stock o indicarlo en el detalle."))
                    package.write({
                        "step_producer_id": producer.id,
                        "box_count": line.box_count,
                        "step_tag_line_ids": [(0, 0, {
                            "producer_id": producer.id,
                            "product_id": product.id,
                            "quantity": quantity,
                            "kilos": line.kilos,
                            "boxes": line.box_count,
                        })],
                    })
                if package.step_tag_state == "created":
                    package.action_step_validate_tag()
        return result

    def action_step_import_fruit_tags(self):
        self.ensure_one()
        if not self.step_fruit_reception_kind or self.state == "done":
            raise ValidationError(_("Seleccione una recepción de fruta sin validar."))
        return {
            "type": "ir.actions.act_window", "name": _("Importar tarjas desde Excel"),
            "res_model": "step.fruit.reception.import", "view_mode": "form",
            "target": "new", "context": {"default_picking_id": self.id},
        }

    def action_prepare_fruit_stock(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM stock_picking WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state in ('done', 'cancel') or not self.step_fruit_reception_kind or self.move_ids:
            raise ValidationError(_('Prepare solo una recepción de fruta abierta sin movimientos previos.'))
        if not self.fruit_tag_line_ids or not self.fruit_fundo_id.partner_id:
            raise ValidationError(_('Importe las tarjas y seleccione su fundo antes de preparar stock.'))
        with self.env.cr.savepoint():
            for line in self.fruit_tag_line_ids:
                if not line.product_id or not line.package_id or line.quantity <= 0 or line.package_id.step_tag_state != 'created':
                    raise ValidationError(_('Cada tarja debe estar creada, con producto y cantidad positiva.'))
                if line.product_id.tracking != 'none' and not line.stock_lot_id:
                    raise ValidationError(_('Indique el lote en cada tarja con producto rastreado.'))
                move = self.env['stock.move'].create({
                    'name': line.tag_number, 'picking_id': self.id, 'company_id': self.company_id.id,
                    'product_id': line.product_id.id, 'product_uom': line.product_id.uom_id.id,
                    'product_uom_qty': line.quantity, 'location_id': self.location_id.id,
                    'location_dest_id': self.location_dest_id.id})
                # Keep each received tag's move alive. Native merging can
                # unlink this move when another tag contains the same product.
                move._action_confirm(merge=False)
                move._do_unreserve()
                self.env['stock.move.line'].create({
                    'move_id': move.id, 'picking_id': self.id, 'product_id': line.product_id.id,
                    'product_uom_id': line.product_id.uom_id.id, 'quantity': line.quantity,
                    'location_id': self.location_id.id, 'location_dest_id': self.location_dest_id.id,
                    'result_package_id': line.package_id.id, 'lot_id': line.stock_lot_id.id,
                    'owner_id': self.fruit_fundo_id.partner_id.id if self.step_fruit_reception_kind == 'process' else False})
        return True


class StepPackingPickingTagLine(models.Model):
    _inherit = "step.packing.picking.tag.line"

    step_scale_profile_id = fields.Many2one(related="picking_id.step_scale_profile_id")
    step_scale_protocol = fields.Selection(related="picking_id.step_scale_protocol")
    step_scale_service_uuid = fields.Char(related="picking_id.step_scale_service_uuid")
    step_scale_characteristic_uuid = fields.Char(related="picking_id.step_scale_characteristic_uuid")
    step_scale_serial_service_uuid = fields.Char(related="picking_id.step_scale_serial_service_uuid")
    step_scale_baud_rate = fields.Integer(related="picking_id.step_scale_baud_rate")
    step_scale_weight_pattern = fields.Char(related="picking_id.step_scale_weight_pattern")
    step_scale_kg_factor = fields.Float(related="picking_id.step_scale_kg_factor")
    step_scale_capture = fields.Char(compute="_compute_step_scale_capture")
    step_scale_read_at = fields.Datetime(string="Última lectura", readonly=True, copy=False)
    step_scale_read_raw = fields.Char(string="Trama de última lectura", readonly=True, copy=False)

    def _compute_step_scale_capture(self):
        for line in self:
            line.step_scale_capture = False

    package_id = fields.Many2one("stock.quant.package", string="Paquete de stock")
    product_id = fields.Many2one("product.product", string="Producto")
    stock_lot_id = fields.Many2one('stock.lot', string='Lote de stock')

    @api.constrains('stock_lot_id', 'product_id', 'picking_id')
    def _check_stock_lot(self):
        for line in self:
            if line.stock_lot_id and (line.stock_lot_id.product_id != line.product_id or line.stock_lot_id.company_id != line.picking_id.company_id):
                raise ValidationError(_('El lote debe pertenecer al producto y a la empresa de la recepción.'))
    gross_kg = fields.Float(string="Peso bruto kg", digits="Stock Weight")
    tare_kg = fields.Float(string="Destare kg", digits="Stock Weight")
    net_kg = fields.Float(string="Peso neto kg", compute="_compute_step_net_kg", digits="Stock Weight")
    box_count = fields.Float(string="Cajas", digits="Product Unit of Measure")

    @api.depends("gross_kg", "tare_kg")
    def _compute_step_net_kg(self):
        for line in self:
            line.net_kg = max(0.0, line.gross_kg - line.tare_kg)

    @api.constrains("gross_kg", "tare_kg", "kilos", "package_id")
    def _check_step_weighing(self):
        for line in self:
            if line.gross_kg or line.tare_kg:
                if line.gross_kg <= line.tare_kg:
                    raise ValidationError(_("El peso bruto de la tarja debe superar el destare."))
                if float_compare(line.kilos, line.net_kg, precision_digits=2):
                    raise ValidationError(_("Los kilos de la tarja no coinciden con su pesaje."))
