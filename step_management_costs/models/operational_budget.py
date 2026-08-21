import re
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .budget_template import MONTH_FIELDS
from .exchange_rate import default_conversion_currency


MONTH_SELECTION = [
    ("may", "Mayo"), ("jun", "Junio"), ("jul", "Julio"), ("aug", "Agosto"),
    ("sep", "Septiembre"), ("oct", "Octubre"), ("nov", "Noviembre"),
    ("dec", "Diciembre"), ("jan", "Enero"), ("feb", "Febrero"),
    ("mar", "Marzo"), ("apr", "Abril"),
]
MONTH_NUMBERS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class StepManagementOperationalBudget(models.Model):
    _name = "step.management.operational.budget"
    _description = "Presupuesto operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Folio", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    description = fields.Char(string="Nombre del presupuesto", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Convertir a",
        default=lambda self: default_conversion_currency(self.env),
        domain="[('active', '=', True)]",
    )
    conversion_rate_type = fields.Selection(
        [("estimated", "Estimado mensual"), ("actual", "Real Odoo")],
        string="Tipo de conversión", default="estimated", required=True,
    )
    conversion_available = fields.Boolean(compute="_compute_conversion")
    conversion_factor = fields.Float(
        string="Factor origen → destino", compute="_compute_conversion", digits=(16, 10)
    )
    conversion_target_value = fields.Float(
        string="Valor moneda destino", compute="_compute_conversion", digits=(16, 6)
    )
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today, tracking=True)
    season = fields.Char(string="Temporada", required=True, tracking=True, help="Ej.: 2026/2027")
    template_id = fields.Many2one(
        "step.management.budget.template", string="Plantilla", required=True, tracking=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", required=True, default=lambda self: self.env.user, tracking=True
    )
    allocation_ids = fields.One2many(
        "step.management.budget.center", "budget_id", string="Centros de costo seleccionados", copy=True
    )
    line_ids = fields.One2many(
        "step.management.budget.line", "budget_id", string="Detalle extrapolado", copy=False
    )
    total_hectares = fields.Float(
        string="Hectáreas presupuestadas", compute="_compute_totals", store=True, digits=(16, 4)
    )
    total_amount = fields.Monetary(
        string="Presupuesto total", compute="_compute_totals", store=True, currency_field="currency_id"
    )
    cost_per_ha = fields.Monetary(
        string="Costo promedio por hectárea", compute="_compute_totals", store=True,
        currency_field="currency_id",
    )
    total_amount_converted = fields.Monetary(
        string="Presupuesto convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    cost_per_ha_converted = fields.Monetary(
        string="Costo/ha convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    line_count = fields.Integer(string="Líneas", compute="_compute_totals", store=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("calculated", "Calculado"),
         ("approved", "Aprobado"), ("closed", "Cerrado"), ("cancelled", "Cancelado")],
        string="Estado", default="draft", required=True, tracking=True, index=True,
    )
    notes = fields.Html(string="Notas y supuestos")
    active = fields.Boolean(default=True)

    @api.depends("allocation_ids.hectares", "line_ids.amount")
    def _compute_totals(self):
        for record in self:
            record.total_hectares = sum(record.allocation_ids.mapped("hectares"))
            record.total_amount = sum(record.line_ids.mapped("amount"))
            record.cost_per_ha = record.total_amount / record.total_hectares if record.total_hectares else 0.0
            record.line_count = len(record.line_ids)

    @api.depends(
        "total_amount", "cost_per_ha", "currency_id", "conversion_currency_id",
        "conversion_rate_type", "date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            total_result = service.get_conversion(
                record.total_amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            hectare_result = service.get_conversion(
                record.cost_per_ha, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            record.conversion_available = total_result["available"]
            record.conversion_factor = total_result["factor"]
            record.conversion_target_value = total_result["target_value"]
            record.total_amount_converted = total_result["amount"]
            record.cost_per_ha_converted = hectare_result["amount"]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.operational.budget"
                ) or _("Nuevo")
        return super().create(vals_list)

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id:
            self.currency_id = self.template_id.currency_id
            self.conversion_currency_id = self.template_id.conversion_currency_id
            self.conversion_rate_type = self.template_id.conversion_rate_type

    def action_generate_lines(self):
        for budget in self:
            if budget.state not in ("draft", "calculated"):
                raise UserError("Sólo puede recalcular un presupuesto en borrador o calculado.")
            if not budget.template_id.line_ids:
                raise UserError("La plantilla no contiene indicadores.")
            if not budget.allocation_ids:
                raise UserError("Seleccione al menos un centro de costo.")
            invalid = budget.allocation_ids.filtered(lambda allocation: allocation.hectares <= 0)
            if invalid:
                raise UserError("Todos los centros seleccionados deben tener hectáreas mayores que cero.")

            budget.line_ids.unlink()
            commands = []
            base_hectares = budget.template_id.base_hectares
            for allocation in budget.allocation_ids:
                scale = allocation.hectares / base_hectares
                for template_line in budget.template_id.line_ids:
                    month_commands = []
                    for month in MONTH_FIELDS:
                        template_quantity = template_line[month] or 0.0
                        if template_quantity:
                            month_commands.append((0, 0, {
                                "month": month,
                                "quantity": template_quantity * scale,
                                "unit_price": template_line.unit_price,
                            }))
                    commands.append((0, 0, {
                        "center_id": allocation.center_id.id,
                        "template_line_id": template_line.id,
                        "category": template_line.category,
                        "group_id": template_line.group_id.id,
                        "indicator": template_line.indicator,
                        "activity": template_line.activity,
                        "product_id": template_line.product_id.id,
                        "uom_id": template_line.uom_id.id,
                        "hectares": allocation.hectares,
                        "quantity_per_ha": template_line.quantity_per_ha,
                        "quantity": template_line.quantity_per_ha * allocation.hectares,
                        "unit_price": template_line.unit_price,
                        "month_ids": month_commands,
                    }))
            budget.write({"line_ids": commands, "state": "calculated"})
            budget.message_post(
                body=_("Presupuesto generado desde la plantilla %s para %s centro(s) y %.2f hectáreas.")
                % (budget.template_id.display_name, len(budget.allocation_ids), budget.total_hectares)
            )

    def action_approve(self):
        for record in self:
            if not record.line_ids:
                raise UserError("Genere el detalle antes de aprobar el presupuesto.")
            record.write({"state": "approved"})

    def action_close(self):
        self.write({"state": "closed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_set_draft(self):
        self.write({"state": "draft"})


class StepManagementBudgetCenter(models.Model):
    _name = "step.management.budget.center"
    _description = "Centro incluido en presupuesto"
    _order = "center_id"

    budget_id = fields.Many2one(
        "step.management.operational.budget", required=True, ondelete="cascade", index=True
    )
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", required=True,
        domain="[('company_id', '=', parent.company_id)]",
    )
    registered_hectares = fields.Float(
        related="center_id.hectares", string="Hectáreas registradas", readonly=True
    )
    hectares = fields.Float(string="Hectáreas a presupuestar", required=True, digits=(16, 4))
    notes = fields.Char(string="Observación")

    @api.onchange("center_id")
    def _onchange_center_id(self):
        if self.center_id:
            self.hectares = self.center_id.hectares

    @api.constrains("hectares")
    def _check_hectares(self):
        for record in self:
            if record.hectares <= 0:
                raise ValidationError("Las hectáreas a presupuestar deben ser mayores que cero.")

    @api.constrains("center_id", "budget_id")
    def _check_unique_center(self):
        for record in self:
            duplicate = self.search_count([
                ("budget_id", "=", record.budget_id.id),
                ("center_id", "=", record.center_id.id),
                ("id", "!=", record.id),
            ])
            if duplicate:
                raise ValidationError("No puede seleccionar dos veces el mismo centro de costo.")


class StepManagementBudgetLine(models.Model):
    _name = "step.management.budget.line"
    _description = "Línea de presupuesto extrapolada"
    _order = "center_id, group_id, category, id"

    budget_id = fields.Many2one(
        "step.management.operational.budget", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="budget_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="budget_id.currency_id", store=True)
    conversion_currency_id = fields.Many2one(related="budget_id.conversion_currency_id")
    conversion_rate_type = fields.Selection(related="budget_id.conversion_rate_type")
    conversion_date = fields.Date(related="budget_id.date")
    center_id = fields.Many2one("step.management.cost.center", string="Centro de costo", required=True, index=True)
    template_line_id = fields.Many2one(
        "step.management.budget.template.line", string="Indicador de origen", ondelete="restrict"
    )
    category = fields.Selection(
        [("labor", "Mano de obra"), ("input", "Insumo agrícola"),
         ("machinery", "Maquinaria"), ("service", "Servicio"), ("other", "Otro")],
        required=True, string="Categoría", index=True,
    )
    group_id = fields.Many2one("step.management.budget.group", string="Grupo", required=True, index=True)
    indicator = fields.Char(string="Indicador / labor", required=True)
    activity = fields.Char(string="Actividad")
    product_id = fields.Many2one("product.product", string="Producto")
    uom_id = fields.Many2one("uom.uom", string="UdM")
    hectares = fields.Float(string="Hectáreas", digits=(16, 4), required=True)
    quantity_per_ha = fields.Float(string="Cantidad/ha", digits=(16, 4))
    quantity = fields.Float(string="Cantidad total", digits=(16, 4))
    unit_price = fields.Monetary(string="Tarifa", currency_field="currency_id")
    amount = fields.Monetary(
        string="Total", compute="_compute_amount", store=True, currency_field="currency_id"
    )
    unit_price_converted = fields.Monetary(
        string="Tarifa convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    amount_converted = fields.Monetary(
        string="Total convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    month_ids = fields.One2many("step.management.budget.month", "budget_line_id", string="Distribución mensual")

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for record in self:
            record.amount = record.quantity * record.unit_price

    @api.depends(
        "unit_price", "amount", "currency_id", "conversion_currency_id",
        "conversion_rate_type", "conversion_date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            unit_result = service.get_conversion(
                record.unit_price, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            amount_result = service.get_conversion(
                record.amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            record.unit_price_converted = unit_result["amount"]
            record.amount_converted = amount_result["amount"]


class StepManagementBudgetMonth(models.Model):
    _name = "step.management.budget.month"
    _description = "Distribución mensual de presupuesto"
    _order = "month, id"

    budget_line_id = fields.Many2one("step.management.budget.line", required=True, ondelete="cascade", index=True)
    budget_id = fields.Many2one(related="budget_line_id.budget_id", store=True, index=True)
    center_id = fields.Many2one(related="budget_line_id.center_id", store=True, index=True)
    group_id = fields.Many2one(related="budget_line_id.group_id", store=True, index=True)
    currency_id = fields.Many2one(related="budget_line_id.currency_id", store=True)
    company_id = fields.Many2one(related="budget_line_id.company_id")
    conversion_currency_id = fields.Many2one(related="budget_line_id.conversion_currency_id")
    conversion_rate_type = fields.Selection(related="budget_line_id.conversion_rate_type")
    conversion_date = fields.Date(string="Mes de conversión", compute="_compute_conversion_date")
    month = fields.Selection(MONTH_SELECTION, string="Mes", required=True, index=True)
    quantity = fields.Float(string="Cantidad", digits=(16, 4))
    unit_price = fields.Monetary(string="Tarifa", currency_field="currency_id")
    amount = fields.Monetary(string="Total", compute="_compute_amount", store=True, currency_field="currency_id")
    unit_price_converted = fields.Monetary(
        string="Tarifa convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    amount_converted = fields.Monetary(
        string="Total convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )

    @api.depends("month", "budget_id.season", "budget_id.date")
    def _compute_conversion_date(self):
        for record in self:
            month_number = MONTH_NUMBERS.get(record.month)
            if not month_number:
                record.conversion_date = record.budget_id.date
                continue
            years = [int(value) for value in re.findall(r"\b\d{4}\b", record.budget_id.season or "")]
            if years:
                year = years[0] if month_number >= 5 else (
                    years[1] if len(years) > 1 else years[0] + 1
                )
            else:
                budget_date = record.budget_id.date or fields.Date.context_today(record)
                year = budget_date.year + (
                    1 if month_number < 5 and budget_date.month >= 5 else 0
                )
            record.conversion_date = date(year, month_number, 1)

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for record in self:
            record.amount = record.quantity * record.unit_price

    @api.depends(
        "unit_price", "amount", "currency_id", "conversion_currency_id",
        "conversion_rate_type", "conversion_date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            unit_result = service.get_conversion(
                record.unit_price, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            amount_result = service.get_conversion(
                record.amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            record.unit_price_converted = unit_result["amount"]
            record.amount_converted = amount_result["amount"]
