"""Native freight operations, migrated in place to descriptive technical names."""

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FreightRoute(models.Model):
    _inherit = "step.freight.route"

    km_from = fields.Float(string="Km desde")
    km_to = fields.Float(string="Km hasta")
    sequence = fields.Integer(string="Secuencia")
    fundo_id = fields.Many2one("step.fundo", string="Fundo")
    # Compatibility aliases for existing imports, views and tariff references.
    # The pre-migration refuses ambiguous values before consolidating columns.
    legacy_origin = fields.Char(related="origin", store=True, readonly=False)
    legacy_destination = fields.Char(related="destination", store=True, readonly=False)
    legacy_company_id = fields.Many2one(related="company_id", store=True, readonly=False)


class FreightTariff(models.Model):
    _inherit = "step.freight.tariff"

    date = fields.Date(string="Fecha")
    sequence = fields.Integer()
    fundo_id = fields.Many2one("step.fundo", string="Fundo")
    legacy_company_id = fields.Many2one("res.company", string="Empresa")
    responsible_id = fields.Many2one("hr.employee", string="Responsable")
    approver_id = fields.Many2one("hr.employee", string="Autoriza")
    freight_carrier_id = fields.Many2one(
        "res.partner", string="Transportista", domain="[('is_freight_carrier', '=', True)]"
    )
    effective_from = fields.Date(string="Vigente desde")
    effective_to = fields.Date(string="Vigente hasta")
    tariff_state = fields.Selection(
        [("status1", "Ingresada"), ("status2", "Autorizada"), ("Vencida", "Vencida")],
        string="Estado", default="status1",
    )
    tariff_line_ids = fields.One2many(
        "step.freight.tariff.line", "tariff_id", string="Líneas de tarifa"
    )


class FreightTariffLine(models.Model):
    _name = "step.freight.tariff.line"
    _description = "Línea de tarifa de flete"
    _order = "sequence, id"

    name = fields.Char(string="Línea", required=True, default="1")
    sequence = fields.Integer(string="Secuencia")
    tariff_id = fields.Many2one(
        "step.freight.tariff", string="Tarifa", required=True, ondelete="cascade"
    )
    route_id = fields.Many2one("step.freight.route", string="Tramo")
    cold_mode_id = fields.Many2one("step.freight.cold.mode", string="Modalidad de frío")
    km_from = fields.Float(related="route_id.km_from", string="Km desde")
    km_to = fields.Float(related="route_id.km_to", string="Km hasta")
    tariff_basis = fields.Selection(
        [("Por UdM", "Por UdM"), ("Por viaje", "Por viaje")], string="Modalidad de tarifa"
    )
    currency_id = fields.Many2one("res.currency", string="Moneda")
    freight_rate = fields.Float(string="Tarifa flete")
    service_product_id = fields.Many2one(
        "product.template", string="Servicio de flete", domain="[('is_flete', '=', True)]"
    )


class FreightOrder(models.Model):
    _inherit = "step.freight.order"

    active = fields.Boolean(string="Activo", default=True)
    sequence = fields.Integer()
    legacy_instructions = fields.Html(string="Instrucciones anteriores", readonly=True)
    legacy_company_id = fields.Many2one("res.company", string="Empresa")
    description = fields.Char(string="Descripción del flete")
    instructions = fields.Text(string="Instrucciones del flete")
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra")
    sale_order_id = fields.Many2one("sale.order", string="Pedido de venta")
    price_list_id = fields.Many2one("step.freight.tariff", string="Lista de tarifa flete")
    detail_ids = fields.One2many(
        "step.freight.order.line", "order_id", string="Detalles"
    )
    cost_ids = fields.One2many(
        "step.freight.order.cost", "order_id", string="Costeo"
    )
    freight_move_id = fields.Many2one("account.move", string="Asiento de flete", readonly=True, copy=False)
    freight_total = fields.Monetary(
        string="Valor total del flete", compute="_compute_freight_total", currency_field="currency_id"
    )

    @api.model
    def _without_blank_detail_creates(self, values):
        values = dict(values)
        if "detail_ids" in values:
            Detail = self.env["step.freight.order.line"]
            values["detail_ids"] = [command for command in values["detail_ids"]
                if not (command[0] == fields.Command.CREATE and Detail._is_blank_values(command[2]))]
        return values

    @api.model_create_multi
    def create(self, values_list):
        return super().create([self._without_blank_detail_creates(values) for values in values_list])

    def write(self, values):
        return super().write(self._without_blank_detail_creates(values))

    @api.depends("detail_ids.freight_value")
    def _compute_freight_total(self):
        for order in self:
            order.freight_total = sum(order.detail_ids.mapped("freight_value"))

    @api.onchange("price_list_id")
    def _onchange_price_list(self):
        for order in self:
            if order.freight_move_id:
                continue
            order.tariff_id = order.price_list_id
            tariff = order.price_list_id
            if tariff and tariff.freight_carrier_id:
                order.freight_carrier_id = tariff.freight_carrier_id
            modes = tariff.tariff_line_ids.mapped("cold_mode_id")
            if len(modes) == 1 and all(line.cold_mode_id for line in tariff.tariff_line_ids):
                order.cold_mode_id = modes
        self._onchange_tariff_context()

    @api.onchange("cold_mode_id", "date", "company_id")
    def _onchange_tariff_context(self):
        for order in self:
            if not order.freight_move_id:
                order.detail_ids._onchange_route_service()

    def _tariff_line_for_detail(self, detail):
        self.ensure_one()
        tariff = self.price_list_id or self.tariff_id
        if not tariff:
            raise UserError(_("Seleccione una lista de tarifa en el encabezado del flete."))
        if tariff.company_id and tariff.company_id != self.company_id:
            raise UserError(_("La tarifa pertenece a otra empresa."))
        day = self.date or fields.Date.context_today(self)
        if (tariff.effective_from and day < tariff.effective_from) or (
            tariff.effective_to and day > tariff.effective_to
        ):
            raise UserError(_("La lista de tarifa no está vigente en la fecha del flete."))
        if not detail.route_id:
            raise UserError(_("Seleccione un tramo en cada línea de detalle."))
        lines = tariff.tariff_line_ids.filtered(
            lambda line: line.route_id == detail.route_id
            and (not line.cold_mode_id or line.cold_mode_id == self.cold_mode_id)
            and (not detail.service_product_id or not line.service_product_id
                 or line.service_product_id == detail.service_product_id)
        )
        if self.cold_mode_id:
            exact = lines.filtered(lambda line: line.cold_mode_id == self.cold_mode_id)
            lines = exact or lines
        if detail.service_product_id:
            exact = lines.filtered(lambda line: line.service_product_id == detail.service_product_id)
            lines = exact or lines
        if len(lines) != 1:
            raise UserError(_(
                "La tarifa '%s' debe tener exactamente una línea para el tramo '%s', "
                "la modalidad de frío y el servicio seleccionados (coincidencias: %s)."
            ) % (tariff.display_name, detail.route_id.display_name, len(lines)))
        return lines

    def action_cost_freight(self):
        for order in self:
            if order.freight_move_id:
                raise UserError(_("El flete ya está contabilizado y no se puede recalcular el costeo."))
            details = order.detail_ids.filtered(lambda line: not line._is_blank_detail())
            if not details:
                raise UserError(_("Agregue al menos una línea en Detalles antes de costear."))
            old_costs = order.cost_ids
            totals = defaultdict(float)
            date = order.date or fields.Date.context_today(order)
            for detail in details:
                tariff_line = order._tariff_line_for_detail(detail)
                product = detail.service_product_id or tariff_line.service_product_id
                if not product and len(old_costs) == 1:
                    product = old_costs.service_product_id
                if not product:
                    raise UserError(_("Indique el servicio de flete en la línea de tarifa o en Detalles."))
                if not product.is_flete:
                    raise UserError(_("El servicio '%s' no está marcado como flete.") % product.display_name)
                quantity = detail.quantity
                if quantity <= 0:
                    raise ValidationError(_("La cantidad del detalle debe ser mayor que cero."))
                # An explicit rate entered in Detalles is part of the quote.
                # Rows created by imports without a rate use the tariff rate.
                price = detail.unit_rate if detail.unit_rate != 0 else tariff_line.freight_rate
                if price <= 0:
                    raise ValidationError(_("La tarifa del detalle debe ser mayor que cero."))
                line_amount = price * (quantity if tariff_line.tariff_basis != "Por viaje" else 1)
                currency = tariff_line.currency_id or order.company_id.currency_id
                total = currency._convert(line_amount, order.company_id.currency_id, order.company_id, date)
                detail.write({
                    "unit_rate": price,
                    "freight_value": total,
                    "service_product_id": product.id,
                })
                totals[product.id] += total
            for product_id, amount in totals.items():
                existing = old_costs.filtered(lambda cost: cost.service_product_id.id == product_id)[:1]
                vals = {"service_product_id": product_id, "freight_cost": amount}
                if existing:
                    existing.write(vals)
                else:
                    self.env["step.freight.order.cost"].create({
                        **vals, "order_id": order.id, "name": str(len(old_costs) + 1),
                    })
            old_costs.filtered(lambda cost: cost.service_product_id.id not in totals).unlink()
            order.message_post(body=_("Costeo calculado desde la lista de tarifa y los detalles."))
        return True

    def action_post_freight(self):
        if not self.env.user.has_group("account.group_account_user"):
            raise UserError(_("Solo un usuario de Contabilidad puede contabilizar fletes."))
        for order in self:
            if order.freight_move_id or self.env["step.freight.accounting"].search_count([
                ("order_id", "=", order.id), ("move_id", "!=", False)
            ]):
                raise UserError(_("Este flete ya tiene un asiento contable."))
            costs = order.cost_ids
            if not costs:
                raise UserError(_("Ejecute el costeo antes de contabilizar el flete."))
            journal = order.company_id.freight_provision_journal_id
            credit_account = journal.default_account_id
            if not journal or journal.company_id != order.company_id or journal.type != "general":
                raise UserError(_("Configure un diario general de provisión en Fletes → Configuración → Ajustes."))
            if not credit_account or not credit_account.account_type.startswith("liability"):
                raise UserError(_("La cuenta predeterminada del diario de fletes debe ser una cuenta de pasivo."))
            carrier = order.freight_carrier_id or order.price_list_id.freight_carrier_id
            if not carrier:
                raise UserError(_("Indique el transportista que se usará como auxiliar del abono."))
            move_lines = []
            debit_total = 0.0
            for cost in costs:
                amount = order.company_id.currency_id.round(cost.freight_cost)
                account = cost.expense_account_id
                if amount <= 0 or not account:
                    raise UserError(_("Cada línea de costeo requiere monto positivo y cuenta de cargo en el producto."))
                if journal.account_control_ids and account not in journal.account_control_ids:
                    raise UserError(_("La cuenta de cargo %s no está permitida en el diario %s.") % (
                        account.display_name, journal.display_name
                    ))
                move_lines.append((0, 0, {
                    "name": cost.service_product_id.display_name,
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
                "name": _("Provisión de flete %s") % order.name,
                "account_id": credit_account.id,
                "debit": 0.0,
                "credit": order.company_id.currency_id.round(debit_total),
                "partner_id": carrier.id,
            }))
            move = self.env["account.move"].create({
                "move_type": "entry", "journal_id": journal.id, "date": order.date,
                "ref": order.name, "line_ids": move_lines,
            })
            move.action_post()
            order.write({"freight_move_id": move.id, "freight_state": "status3"})
            self.env["step.freight.accounting"].create({
                "name": order.name, "order_id": order.id,
                "accounting_date": move.date, "move_id": move.id,
            })
        return True


class FreightOrderDetail(models.Model):
    _name = "step.freight.order.line"
    _description = "Detalle de orden de flete"
    _order = "sequence, id"

    name = fields.Char(string="Línea", required=True, default="1")
    sequence = fields.Integer(string="Secuencia")
    order_id = fields.Many2one("step.freight.order", string="Flete", required=True, ondelete="cascade")
    vehicle_id = fields.Many2one(
        "fleet.vehicle", string="Camión", domain="[('category_id.name', 'ilike', 'carga')]"
    )
    driver_id = fields.Many2one(
        "res.partner", string="Chofer", domain="[('step_chofer', '=', True)]"
    )
    route_id = fields.Many2one("step.freight.route", string="Tramo")
    km_to = fields.Float(related="route_id.km_to", string="Km hasta")
    cargo_description = fields.Char(string="Detalle carga")
    delivery_reference = fields.Char(string="Guía referencia")
    uom_id = fields.Many2one("uom.uom", string="Unidad")
    quantity = fields.Float(string="Cantidad", default=1.0)
    unit_rate = fields.Float(string="Tarifa")
    freight_value = fields.Float(string="Valor del flete")
    service_product_id = fields.Many2one("product.template", string="Servicio de flete", domain="[('is_flete', '=', True)]")

    @api.model
    def _is_blank_values(self, values):
        # Only ignore a new row with untouched defaults. A row with any real
        # input must remain visible and go through the usual validations.
        defaults = {"name": "1", "quantity": 1.0}
        non_business = {"id", "order_id", "sequence"}
        for key, value in values.items():
            if key in defaults:
                if value not in (False, None, defaults[key]):
                    return False
                if key == "quantity" and value != 1.0:
                    return False
            elif key in non_business:
                if key == "sequence" and value:
                    return False
            elif value:
                return False
        return True

    def _is_blank_detail(self):
        self.ensure_one()
        return self._is_blank_values({name: self[name] for name in (
            "name", "quantity", "sequence", "vehicle_id", "driver_id", "route_id",
            "service_product_id", "cargo_description", "delivery_reference", "uom_id",
            "unit_rate", "freight_value")})

    @api.onchange("route_id", "service_product_id")
    def _onchange_route_service(self):
        for detail in self:
            if detail.order_id and detail.route_id:
                try:
                    line = detail.order_id._tariff_line_for_detail(detail)
                except UserError:
                    detail.unit_rate = 0.0
                else:
                    detail.unit_rate = line.freight_rate
                    if not detail.service_product_id and line.service_product_id:
                        detail.service_product_id = line.service_product_id
                    if not detail.uom_id and detail.service_product_id:
                        detail.uom_id = detail.service_product_id.uom_id
            detail._onchange_amount()

    @api.onchange("quantity", "unit_rate")
    def _onchange_amount(self):
        for detail in self:
            amount = detail.quantity * detail.unit_rate
            order = detail.order_id
            if order and detail.route_id:
                try:
                    line = order._tariff_line_for_detail(detail)
                except UserError:
                    pass  # Explicit validation remains in Calcular costeo.
                else:
                    if line.tariff_basis == "Por viaje":
                        amount = detail.unit_rate
                    company = order.company_id or self.env.company
                    currency = line.currency_id or company.currency_id
                    amount = currency._convert(amount, company.currency_id, company,
                                               order.date or fields.Date.context_today(order))
            detail.freight_value = amount


class FreightOrderCost(models.Model):
    _name = "step.freight.order.cost"
    _inherit = "analytic.mixin"
    _description = "Costeo de orden de flete"
    _order = "sequence, id"

    name = fields.Char(string="Línea", required=True, default="1")
    sequence = fields.Integer(string="Secuencia")
    order_id = fields.Many2one("step.freight.order", string="Flete", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", string="Empresa")
    service_product_id = fields.Many2one("product.template", string="Servicio flete")
    freight_cost = fields.Float(string="Costo flete")
    expense_account_id = fields.Many2one(
        "account.account", string="Cuenta de cargo", compute="_compute_expense_account", store=True
    )
    legacy_distribution_model_id = fields.Many2one(
        "account.analytic.distribution.model", string="Distribución analítica anterior"
    )
    distribution_model_id = fields.Many2one(
        "account.analytic.distribution.model", string="Modelo de distribución analítica"
    )
    analytic_distribution = fields.Json(string="Distribución analítica")

    @api.depends("service_product_id", "order_id.company_id")
    def _compute_expense_account(self):
        for cost in self:
            product = cost.service_product_id.with_company(cost.order_id.company_id)
            cost.expense_account_id = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id

    @api.onchange("distribution_model_id")
    def _onchange_distribution_model(self):
        for cost in self:
            if cost.distribution_model_id:
                cost.analytic_distribution = cost.distribution_model_id.analytic_distribution


class FreightCarrierPartner(models.Model):
    _inherit = "res.partner"

    is_freight_carrier = fields.Boolean(string="Transportista de fletes")


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
