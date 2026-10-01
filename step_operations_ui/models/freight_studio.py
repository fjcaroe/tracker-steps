"""Code-owned freight workflow using the existing Studio tables and columns.

The technical names deliberately match the fields already used in Desarrollo.
Keeping them avoids losing tariff and freight records during the Studio migration.
"""

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FreightRoute(models.Model):
    _inherit = "x_tramo_de_flete"

    x_studio_km_desde = fields.Float(string="Km desde")
    x_studio_km_hasta = fields.Float(string="Km hasta")


class FreightTariff(models.Model):
    _inherit = "x_tarifa_de_fletes"

    x_studio_fecha = fields.Date(string="Fecha")
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo")
    x_studio_empresa = fields.Many2one("res.company", string="Empresa")
    x_studio_responsable = fields.Many2one("hr.employee", string="Responsable")
    x_studio_autoriza = fields.Many2one("hr.employee", string="Autoriza")
    x_studio_transportista = fields.Many2one("res.partner", string="Transportista")
    x_studio_vigencia_desde = fields.Date(string="Vigente desde")
    x_studio_vigencia_hasta = fields.Date(string="Vigente hasta")
    x_studio_selection_field_8tm_1jhk3i2t3 = fields.Selection(
        [("status1", "Ingresada"), ("status2", "Autorizada"), ("Vencida", "Vencida")],
        string="Estado", default="status1",
    )
    x_studio_one2many_field_61q_1jhk3j03r = fields.One2many(
        "x_tarifa_de_fletes_line_57b07", "x_tarifa_de_fletes_id", string="Líneas de tarifa"
    )


class FreightTariffLine(models.Model):
    _name = "x_tarifa_de_fletes_line_57b07"
    _description = "Línea de tarifa de flete"
    _order = "x_studio_sequence, id"

    x_name = fields.Char(string="Línea", required=True, default="1")
    x_studio_sequence = fields.Integer(string="Secuencia")
    x_tarifa_de_fletes_id = fields.Many2one(
        "x_tarifa_de_fletes", string="Tarifa", required=True, ondelete="cascade"
    )
    x_studio_tramo_de_flete = fields.Many2one("x_tramo_de_flete", string="Tramo")
    x_studio_modalidad_de_fro = fields.Many2one("x_modalidad_de_frio", string="Modalidad de frío")
    x_studio_km_desde = fields.Float(related="x_studio_tramo_de_flete.x_studio_km_desde", string="Km desde")
    x_studio_km_hasta = fields.Float(related="x_studio_tramo_de_flete.x_studio_km_hasta", string="Km hasta")
    x_studio_modalidad_de_tarifa = fields.Selection(
        [("Por UdM", "Por UdM"), ("Por viaje", "Por viaje")], string="Modalidad de tarifa"
    )
    x_studio_moneda = fields.Many2one("res.currency", string="Moneda")
    x_studio_tarifa_flete = fields.Float(string="Tarifa flete")
    service_product_id = fields.Many2one(
        "product.template", string="Servicio de flete", domain="[('is_flete', '=', True)]"
    )


class FreightOrder(models.Model):
    _inherit = "x_orden_de_flete"

    x_active = fields.Boolean(string="Activo", default=True)
    x_studio_empresa = fields.Many2one("res.company", string="Empresa")
    x_studio_orden_de_flete = fields.Char(string="Descripción del flete")
    x_studio_instrucciones_del_flete = fields.Text(string="Instrucciones del flete")
    x_studio_orden_de_compra = fields.Many2one("purchase.order", string="Orden de compra")
    x_studio_pedido_de_venta = fields.Many2one("sale.order", string="Pedido de venta")
    x_studio_lista_de_tarifa_flete = fields.Many2one("x_tarifa_de_fletes", string="Lista de tarifa flete")
    x_studio_one2many_field_9na_1jhk4lspn = fields.One2many(
        "x_orden_de_flete_line_709f3", "x_orden_de_flete_id", string="Detalles"
    )
    x_studio_one2many_field_8gj_1jhk6aj15 = fields.One2many(
        "x_orden_de_flete_line_72953", "x_orden_de_flete_id", string="Costeo"
    )
    freight_move_id = fields.Many2one("account.move", string="Asiento de flete", readonly=True, copy=False)
    freight_total = fields.Monetary(
        string="Valor total del flete", compute="_compute_freight_total", currency_field="currency_id"
    )

    @api.depends("x_studio_one2many_field_9na_1jhk4lspn.x_studio_valor_del_flete")
    def _compute_freight_total(self):
        for order in self:
            order.freight_total = sum(order.x_studio_one2many_field_9na_1jhk4lspn.mapped("x_studio_valor_del_flete"))

    @api.onchange("x_studio_lista_de_tarifa_flete")
    def _onchange_studio_tariff(self):
        for order in self:
            order.tariff_id = order.x_studio_lista_de_tarifa_flete
            tariff = order.x_studio_lista_de_tarifa_flete
            if tariff and tariff.x_studio_transportista:
                order.x_studio_transportista = tariff.x_studio_transportista

    def _tariff_line_for_detail(self, detail):
        self.ensure_one()
        tariff = self.x_studio_lista_de_tarifa_flete or self.tariff_id
        if not tariff:
            raise UserError(_("Seleccione una lista de tarifa en el encabezado del flete."))
        if tariff.company_id and tariff.company_id != self.company_id:
            raise UserError(_("La tarifa pertenece a otra empresa."))
        day = self.x_studio_fecha or fields.Date.context_today(self)
        if (tariff.x_studio_vigencia_desde and day < tariff.x_studio_vigencia_desde) or (
            tariff.x_studio_vigencia_hasta and day > tariff.x_studio_vigencia_hasta
        ):
            raise UserError(_("La lista de tarifa no está vigente en la fecha del flete."))
        if not detail.x_studio_tramo:
            raise UserError(_("Seleccione un tramo en cada línea de detalle."))
        lines = tariff.x_studio_one2many_field_61q_1jhk3j03r.filtered(
            lambda line: line.x_studio_tramo_de_flete == detail.x_studio_tramo
            and (not line.x_studio_modalidad_de_fro or line.x_studio_modalidad_de_fro == self.cold_mode_id)
            and (not detail.service_product_id or line.service_product_id == detail.service_product_id)
        )
        if self.cold_mode_id:
            exact = lines.filtered(lambda line: line.x_studio_modalidad_de_fro == self.cold_mode_id)
            lines = exact or lines
        if len(lines) != 1:
            raise UserError(_(
                "La tarifa '%s' debe tener exactamente una línea para el tramo '%s', "
                "la modalidad de frío y el servicio seleccionados (coincidencias: %s)."
            ) % (tariff.display_name, detail.x_studio_tramo.display_name, len(lines)))
        return lines

    def action_cost_freight(self):
        for order in self:
            if order.freight_move_id:
                raise UserError(_("El flete ya está contabilizado y no se puede recalcular el costeo."))
            if not order.x_studio_one2many_field_9na_1jhk4lspn:
                raise UserError(_("Agregue al menos una línea en Detalles antes de costear."))
            old_costs = order.x_studio_one2many_field_8gj_1jhk6aj15
            totals = defaultdict(float)
            date = order.x_studio_fecha or fields.Date.context_today(order)
            for detail in order.x_studio_one2many_field_9na_1jhk4lspn:
                tariff_line = order._tariff_line_for_detail(detail)
                product = detail.service_product_id or tariff_line.service_product_id
                if not product and len(old_costs) == 1:
                    product = old_costs.x_studio_servicio_flete
                if not product:
                    raise UserError(_("Indique el servicio de flete en la línea de tarifa o en Detalles."))
                if not product.is_flete:
                    raise UserError(_("El servicio '%s' no está marcado como flete.") % product.display_name)
                quantity = detail.x_studio_cantidad
                if quantity <= 0:
                    raise ValidationError(_("La cantidad del detalle debe ser mayor que cero."))
                price = tariff_line.x_studio_tarifa_flete
                if price <= 0:
                    raise ValidationError(_("La tarifa del detalle debe ser mayor que cero."))
                line_amount = price * (quantity if tariff_line.x_studio_modalidad_de_tarifa != "Por viaje" else 1)
                currency = tariff_line.x_studio_moneda or order.company_id.currency_id
                total = currency._convert(line_amount, order.company_id.currency_id, order.company_id, date)
                detail.write({
                    "x_studio_tarifa": price,
                    "x_studio_valor_del_flete": total,
                    "service_product_id": product.id,
                })
                totals[product.id] += total
            for product_id, amount in totals.items():
                existing = old_costs.filtered(lambda cost: cost.x_studio_servicio_flete.id == product_id)[:1]
                vals = {"x_studio_servicio_flete": product_id, "x_studio_costo_flete": amount}
                if existing:
                    existing.write(vals)
                else:
                    self.env["x_orden_de_flete_line_72953"].create({
                        **vals, "x_orden_de_flete_id": order.id, "x_name": str(len(old_costs) + 1),
                    })
            old_costs.filtered(lambda cost: cost.x_studio_servicio_flete.id not in totals).unlink()
            order.message_post(body=_("Costeo calculado desde la lista de tarifa y los detalles."))
        return True

    def action_post_freight(self):
        if not self.env.user.has_group("account.group_account_user"):
            raise UserError(_("Solo un usuario de Contabilidad puede contabilizar fletes."))
        for order in self:
            if order.freight_move_id or self.env["x_contabilizacion_de_f"].search_count([
                ("order_id", "=", order.id), ("move_id", "!=", False)
            ]):
                raise UserError(_("Este flete ya tiene un asiento contable."))
            costs = order.x_studio_one2many_field_8gj_1jhk6aj15
            if not costs:
                raise UserError(_("Ejecute el costeo antes de contabilizar el flete."))
            journal = order.company_id.freight_provision_journal_id
            credit_account = journal.default_account_id
            if not journal or journal.company_id != order.company_id or journal.type != "general":
                raise UserError(_("Configure un diario general de provisión en Fletes → Configuración → Ajustes."))
            if not credit_account or not credit_account.account_type.startswith("liability"):
                raise UserError(_("La cuenta predeterminada del diario de fletes debe ser una cuenta de pasivo."))
            carrier = order.x_studio_transportista or order.x_studio_lista_de_tarifa_flete.x_studio_transportista
            if not carrier:
                raise UserError(_("Indique el transportista que se usará como auxiliar del abono."))
            move_lines = []
            debit_total = 0.0
            for cost in costs:
                amount = order.company_id.currency_id.round(cost.x_studio_costo_flete)
                account = cost.x_studio_cuenta
                if amount <= 0 or not account:
                    raise UserError(_("Cada línea de costeo requiere monto positivo y cuenta de cargo en el producto."))
                if journal.account_control_ids and account not in journal.account_control_ids:
                    raise UserError(_("La cuenta de cargo %s no está permitida en el diario %s.") % (
                        account.display_name, journal.display_name
                    ))
                move_lines.append((0, 0, {
                    "name": cost.x_studio_servicio_flete.display_name,
                    "account_id": account.id,
                    "debit": amount,
                    "credit": 0.0,
                    "partner_id": carrier.id,
                    "analytic_distribution": cost.analytic_distribution or False,
                }))
                debit_total += amount
            if journal.account_control_ids and credit_account not in journal.account_control_ids:
                raise UserError(_("La cuenta de abono %s no está permitida en el diario %s.") % (
                    credit_account.display_name, journal.display_name
                ))
            move_lines.append((0, 0, {
                "name": _("Provisión de flete %s") % order.x_name,
                "account_id": credit_account.id,
                "debit": 0.0,
                "credit": order.company_id.currency_id.round(debit_total),
                "partner_id": carrier.id,
            }))
            move = self.env["account.move"].create({
                "move_type": "entry", "journal_id": journal.id, "date": order.x_studio_fecha,
                "ref": order.x_name, "line_ids": move_lines,
            })
            move.action_post()
            order.write({"freight_move_id": move.id, "x_studio_selection_field_4ag_1jhk4c7s5": "status3"})
            self.env["x_contabilizacion_de_f"].create({
                "x_name": order.x_name, "order_id": order.id,
                "accounting_date": move.date, "move_id": move.id,
            })
        return True


class FreightOrderDetail(models.Model):
    _name = "x_orden_de_flete_line_709f3"
    _description = "Detalle de orden de flete"
    _order = "x_studio_sequence, id"

    x_name = fields.Char(string="Línea", required=True, default="1")
    x_studio_sequence = fields.Integer(string="Secuencia")
    x_orden_de_flete_id = fields.Many2one("x_orden_de_flete", string="Flete", required=True, ondelete="cascade")
    x_studio_camin = fields.Many2one("fleet.vehicle", string="Camión")
    x_studio_chofer = fields.Many2one("res.partner", string="Chofer")
    x_studio_tramo = fields.Many2one("x_tramo_de_flete", string="Tramo")
    x_studio_km_hasta = fields.Float(related="x_studio_tramo.x_studio_km_hasta", string="Km hasta")
    x_studio_detalle_carga = fields.Char(string="Detalle carga")
    x_studio_gua_referencia = fields.Char(string="Guía referencia")
    x_studio_unidad = fields.Many2one("uom.uom", string="Unidad")
    x_studio_cantidad = fields.Float(string="Cantidad", default=1.0)
    x_studio_tarifa = fields.Float(string="Tarifa")
    x_studio_valor_del_flete = fields.Float(string="Valor del flete")
    service_product_id = fields.Many2one("product.template", string="Servicio de flete", domain="[('is_flete', '=', True)]")

    @api.onchange("x_studio_tramo", "service_product_id")
    def _onchange_route_service(self):
        for detail in self:
            if detail.x_orden_de_flete_id and detail.x_studio_tramo:
                try:
                    line = detail.x_orden_de_flete_id._tariff_line_for_detail(detail)
                except UserError:
                    detail.x_studio_tarifa = 0.0
                else:
                    detail.x_studio_tarifa = line.x_studio_tarifa_flete

    @api.onchange("x_studio_cantidad", "x_studio_tarifa")
    def _onchange_amount(self):
        for detail in self:
            detail.x_studio_valor_del_flete = detail.x_studio_cantidad * detail.x_studio_tarifa


class FreightOrderCost(models.Model):
    _name = "x_orden_de_flete_line_72953"
    _description = "Costeo de orden de flete"
    _order = "x_studio_sequence, id"

    x_name = fields.Char(string="Línea", required=True, default="1")
    x_studio_sequence = fields.Integer(string="Secuencia")
    x_orden_de_flete_id = fields.Many2one("x_orden_de_flete", string="Flete", required=True, ondelete="cascade")
    x_studio_servicio_flete = fields.Many2one("product.template", string="Servicio flete")
    x_studio_costo_flete = fields.Float(string="Costo flete")
    x_studio_cuenta = fields.Many2one(
        "account.account", string="Cuenta de cargo", compute="_compute_expense_account", store=True
    )
    x_studio_distribucin_analtica = fields.Many2one(
        "account.analytic.distribution.model", string="Distribución analítica (Studio)"
    )
    x_studio_modelo_distr_analtica = fields.Many2one(
        "account.analytic.distribution.model", string="Modelo de distribución analítica"
    )
    analytic_distribution = fields.Json(string="Distribución analítica")

    @api.depends("x_studio_servicio_flete")
    def _compute_expense_account(self):
        for cost in self:
            product = cost.x_studio_servicio_flete.with_company(cost.x_orden_de_flete_id.company_id)
            cost.x_studio_cuenta = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id

    @api.onchange("x_studio_modelo_distr_analtica")
    def _onchange_distribution_model(self):
        for cost in self:
            if cost.x_studio_modelo_distr_analtica:
                cost.analytic_distribution = cost.x_studio_modelo_distr_analtica.analytic_distribution


class FreightCompany(models.Model):
    _inherit = "res.company"

    freight_provision_journal_id = fields.Many2one(
        "account.journal", string="Diario de provisión de fletes",
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
    )


class FreightSettings(models.TransientModel):
    _inherit = "res.config.settings"

    freight_provision_journal_id = fields.Many2one(
        related="company_id.freight_provision_journal_id", readonly=False,
        string="Diario de provisión de fletes",
    )
