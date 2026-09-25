"""Fase 6/7 — necesidades de stock consolidadas (semana / mes / temporada).

Consolida la demanda de materiales de una temporada a partir de fuentes
**aprobadas** y conciliadas:

- presupuestos operacionales (líneas de categoría «insumo agrícola» con
  producto y distribución mensual);
- programas fitosanitarios / de fertilización (aplicaciones expandidas por
  centro de costo, con su semana).

Regla de la puerta de salida de Fase 6: la consolidación concilia con sus
fuentes y no duplica — cada fuente aporta en su propia columna
(`budget_quantity` / `program_quantity`) y la suma por período reproduce el
total de la fuente. No se acopla a la Orden de Producción ni a módulos de OT
(puentes operacionales aparte).

Corte 1 post Fase 6 (respuesta del cliente): la necesidad se cruza con
existencias reales de Odoo para obtener el faltante. El cruce es explícito y
auditable — se elige almacén y métrica de disponibilidad (nunca se mezclan
`qty_available`/reservado/`virtual_available` bajo una sola etiqueta) y se
registra el instante del cálculo.
"""

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round

from .period_service import MONTH_KEY_TO_NUMBER

MONTH_NUMBER_TO_KEY = {number: key for key, number in MONTH_KEY_TO_NUMBER.items()}
# Orden de la temporada (mayo = 1 … abril = 12) para presentar los meses.
SEASON_MONTH_ORDER = {
    5: 1, 6: 2, 7: 3, 8: 4, 9: 5, 10: 6, 11: 7, 12: 8, 1: 9, 2: 10, 3: 11, 4: 12,
}
MONTH_LABELS = {
    "may": "Mayo", "jun": "Junio", "jul": "Julio", "aug": "Agosto",
    "sep": "Septiembre", "oct": "Octubre", "nov": "Noviembre", "dec": "Diciembre",
    "jan": "Enero", "feb": "Febrero", "mar": "Marzo", "apr": "Abril",
}
NO_WEEK_KEY = "SIN-SEM"

BUDGET_SOURCE_STATES = ("approved", "closed")
PROGRAM_SOURCE_STATES = ("approved",)


class StepManagementStockRequirement(models.Model):
    _name = "step.management.stock.requirement"
    _description = "Necesidades de stock consolidadas"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True, tracking=True,
    )
    season = fields.Char(string="Temporada", required=True, tracking=True, help="Ej.: 2026/2027")
    date = fields.Date(
        string="Fecha", required=True, default=fields.Date.context_today, tracking=True,
    )
    granularity = fields.Selection(
        [("week", "Semana"), ("month", "Mes"), ("season", "Temporada")],
        string="Granularidad", required=True, default="week", tracking=True,
    )
    include_budgets = fields.Boolean(string="Incluir presupuestos", default=True)
    include_programs = fields.Boolean(string="Incluir programas", default=True)
    budget_ids = fields.Many2many(
        "step.management.operational.budget", "step_management_stock_req_budget_rel",
        "requirement_id", "budget_id", string="Presupuestos",
        domain="[('company_id', '=', company_id), ('state', 'in', ('approved', 'closed'))]",
        help="Vacío = todos los presupuestos aprobados/cerrados de la temporada.",
    )
    program_ids = fields.Many2many(
        "step.management.crop.program", "step_management_stock_req_program_rel",
        "requirement_id", "program_id", string="Programas",
        domain="[('company_id', '=', company_id), ('state', '=', 'approved')]",
        help="Vacío = todos los programas aprobados de la temporada.",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse", string="Almacén", check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Vacío = todos los almacenes de la empresa (alcance de "
             "compañía). Explícito para que el cruce con inventario nunca "
             "dependa de una ubicación implícita.",
    )
    availability_metric = fields.Selection(
        [("on_hand", "En existencia (qty_available)"),
         ("free", "Libre (existencia − reservado)"),
         ("forecasted", "Pronosticada (virtual_available)")],
        string="Métrica de disponibilidad", default="on_hand", required=True,
        help="En existencia: stock físico actual. Libre: existencia menos "
             "lo reservado por otros movimientos. Pronosticada: existencia "
             "+ entradas previstas − salidas previstas. No se mezclan bajo "
             "una sola etiqueta.",
    )
    computed_at = fields.Datetime(
        string="Calculado el", readonly=True, copy=False,
        help="Instante del último «Calcular»: la disponibilidad de "
             "inventario es una foto de ese momento.",
    )
    line_ids = fields.One2many(
        "step.management.stock.requirement.line", "requirement_id", string="Detalle",
        copy=False,
    )
    line_count = fields.Integer(compute="_compute_line_count", store=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("computed", "Calculado")],
        string="Estado", default="draft", required=True, index=True, tracking=True,
    )
    notes = fields.Html(string="Notas")
    active = fields.Boolean(default=True)

    @api.depends("line_ids")
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.stock.requirement"
                ) or _("Nuevo")
        return super().create(vals_list)

    @api.constrains("budget_ids", "program_ids", "company_id")
    def _check_source_company(self):
        for record in self:
            bad_budgets = record.budget_ids.filtered(
                lambda b: b.company_id != record.company_id
            )
            bad_programs = record.program_ids.filtered(
                lambda p: p.company_id != record.company_id
            )
            if bad_budgets or bad_programs:
                names = (
                    bad_budgets.mapped("display_name")
                    + bad_programs.mapped("display_name")
                )
                raise ValidationError(_(
                    "Las fuentes deben pertenecer a la empresa %(company)s: "
                    "%(names)s"
                ) % {
                    "company": record.company_id.display_name,
                    "names": ", ".join(names),
                })

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _source_budgets(self):
        self.ensure_one()
        if self.budget_ids:
            return self.budget_ids
        return self.env["step.management.operational.budget"].search([
            ("company_id", "=", self.company_id.id),
            ("season", "=", self.season),
            ("state", "in", list(BUDGET_SOURCE_STATES)),
        ])

    def _source_programs(self):
        self.ensure_one()
        if self.program_ids:
            return self.program_ids
        return self.env["step.management.crop.program"].search([
            ("company_id", "=", self.company_id.id),
            ("season", "=", self.season),
            ("state", "in", list(PROGRAM_SOURCE_STATES)),
        ])

    def _period_from_month_key(self, month_key):
        """(period_key, period_label, period_index) para una clave de mes."""
        number = MONTH_KEY_TO_NUMBER.get(month_key, 0)
        if self.granularity == "season":
            return self.season, self.season, 0
        return month_key, MONTH_LABELS.get(month_key, month_key), SEASON_MONTH_ORDER.get(number, 99)

    def _period_from_week_number(self, week_number):
        """(period_key, period_label, period_index) para un nº de semana ISO."""
        if self.granularity == "season":
            return self.season, self.season, 0
        located = self.env["step.management.period.service"].week_of_season(
            self.season, week_number
        )
        if not located:
            return NO_WEEK_KEY, _("Sin semana"), 999
        if self.granularity == "month":
            month_key = MONTH_NUMBER_TO_KEY.get(located["month"])
            return self._period_from_month_key(month_key)
        return located["label"], located["label"], located["index"]

    # ------------------------------------------------------------------
    # Cruce con inventario real (Corte 1 post Fase 6)
    # ------------------------------------------------------------------
    def _stock_location_domain(self):
        """Ubicaciones internas a considerar: las del almacén elegido, o
        todas las de la empresa si no se eligió ninguno (alcance explícito
        de compañía, nunca implícito)."""
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("location_id.usage", "=", "internal"),
        ]
        if self.warehouse_id:
            domain.append(
                ("location_id", "child_of", self.warehouse_id.view_location_id.id)
            )
        return domain

    def _reserved_quantity(self, product):
        """Cantidad reservada del producto en las ubicaciones en alcance.

        Lectura agregada de sólo consulta; `sudo()` porque los roles de
        Gestión y Costos no tienen por qué tener acceso al modelo de
        inventario para poder leer este cruce."""
        self.ensure_one()
        domain = self._stock_location_domain() + [("product_id", "=", product.id)]
        quants = self.env["stock.quant"].sudo().search(domain)
        return sum(quants.mapped("reserved_quantity"))

    def _read_product_availability(self, product):
        """Disponibilidad del producto según `availability_metric`, en el
        alcance de almacén/compañía elegido. Cada métrica tiene su propio
        significado; nunca se mezclan (D-decisión Corte 1).

        `sudo()`: `qty_available`/`virtual_available` pueden depender
        internamente de otros modelos instalados (p. ej. `mrp.bom` para
        kits fantasma) a los que un usuario de Gestión y Costos no tiene
        por qué tener acceso; esta es una lectura agregada de sólo
        consulta, no una vía de escritura."""
        self.ensure_one()
        context = {}
        if self.warehouse_id:
            context["warehouse"] = self.warehouse_id.id
        scoped = product.sudo().with_company(self.company_id).with_context(**context)
        if self.availability_metric == "forecasted":
            return scoped.virtual_available
        on_hand = scoped.qty_available
        if self.availability_metric == "free":
            return on_hand - self._reserved_quantity(product)
        return on_hand

    def _committed_quantity(self, product):
        """Corte V2 C — cantidad comprometida: pendiente de facturar en
        órdenes de compra **confirmadas** (`state='purchase'`; borrador,
        enviada y cancelada quedan fuera). Facturada por completo → 0
        (nada pendiente); facturada parcialmente → sólo el remanente.
        Lectura agregada de sólo consulta (`sudo()`, mismo motivo que
        `_read_product_availability`: Compras puede no estar accesible al
        rol de Gestión y Costos)."""
        self.ensure_one()
        lines = self.env["purchase.order.line"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("product_id", "=", product.id),
            ("state", "=", "purchase"),
        ])
        total = 0.0
        pending_lines = self.env["purchase.order.line"]
        for line in lines:
            remaining = line.product_qty - line.qty_invoiced
            if remaining <= 0:
                continue
            total += line.product_uom.sudo()._compute_quantity(
                remaining, product.uom_id, raise_if_failure=False,
            )
            pending_lines |= line
        return total, pending_lines

    def _bucket_quantity(self, product, source_uom, quantity, source_label):
        """Convierte `quantity` (en `source_uom`) a `product.uom_id` antes de
        acumularla en el bucket de consolidación (R2). La disponibilidad de
        Odoo se expresa siempre en la UdM del producto; sumar sin convertir
        puede producir faltantes incorrectos cuando presupuesto y programa
        usan UdM distintas mientras son compatibles."""
        self.ensure_one()
        if not quantity:
            return 0.0
        if not source_uom:
            raise UserError(_(
                "%(source)s del producto %(product)s no tiene unidad de "
                "medida: no se puede convertir a la UdM del producto "
                "(%(target)s) para consolidar."
            ) % {
                "source": source_label, "product": product.display_name,
                "target": product.uom_id.display_name,
            })
        try:
            return source_uom._compute_quantity(
                quantity, product.uom_id, raise_if_failure=True,
            )
        except UserError as exc:
            raise UserError(_(
                "%(source)s del producto %(product)s está en «%(uom)s», que "
                "no es de la misma categoría que la UdM del producto "
                "(«%(target)s»). Corrija la UdM de la fuente o del producto "
                "antes de calcular."
            ) % {
                "source": source_label, "product": product.display_name,
                "uom": source_uom.display_name,
                "target": product.uom_id.display_name,
            }) from exc

    def action_compute(self):
        period = self.env["step.management.period.service"]
        for requirement in self:
            requirement.line_ids.unlink()
            # bucket[(product_id, period_key)] = {label, index, budget, program, uom_id}
            buckets = {}

            def bucket(product, period_key, period_label, period_index):
                key = (product.id, period_key)
                data = buckets.setdefault(key, {
                    "product_id": product.id,
                    "period_key": period_key,
                    "period_label": period_label,
                    "period_index": period_index,
                    "uom_id": product.uom_id.id,
                    "budget_quantity": 0.0,
                    "program_quantity": 0.0,
                })
                return data

            if requirement.include_budgets:
                for budget in requirement._source_budgets():
                    for line in budget.line_ids:
                        if line.category != "input" or not line.product_id:
                            continue
                        if not line.month_ids:
                            continue
                        month_values = {
                            month.month: month.quantity for month in line.month_ids
                        }
                        if requirement.granularity == "week":
                            rounding = line.uom_id.rounding or 0.01
                            weeks = period.distribute_monthly_to_weeks(
                                requirement.season, month_values, rounding=rounding
                            )
                            for position, week in enumerate(weeks, start=1):
                                if not week["quantity"]:
                                    continue
                                data = bucket(
                                    line.product_id, week["label"], week["label"],
                                    position,
                                )
                                data["budget_quantity"] += requirement._bucket_quantity(
                                    line.product_id, line.uom_id, week["quantity"],
                                    _("El presupuesto"),
                                )
                        else:
                            for month_key, quantity in month_values.items():
                                if not quantity:
                                    continue
                                p_key, p_label, p_index = requirement._period_from_month_key(month_key)
                                data = bucket(
                                    line.product_id, p_key, p_label, p_index,
                                )
                                data["budget_quantity"] += requirement._bucket_quantity(
                                    line.product_id, line.uom_id, quantity,
                                    _("El presupuesto"),
                                )

            if requirement.include_programs:
                for program in requirement._source_programs():
                    for application in program.application_ids:
                        if not application.product_id:
                            continue
                        p_key, p_label, p_index = requirement._period_from_week_number(
                            application.week_number
                        )
                        data = bucket(
                            application.product_id, p_key, p_label, p_index,
                        )
                        data["program_quantity"] += requirement._bucket_quantity(
                            application.product_id, application.uom_id,
                            application.quantity, _("El programa"),
                        )

            availability_by_product = {}
            committed_by_product = {}
            committed_lines_by_product = {}
            product_model = self.env["product.product"]
            for data in buckets.values():
                product_id = data["product_id"]
                if product_id not in availability_by_product:
                    product = product_model.browse(product_id)
                    availability_by_product[product_id] = (
                        requirement._read_product_availability(product)
                    )
                    committed_qty, committed_lines = requirement._committed_quantity(product)
                    committed_by_product[product_id] = committed_qty
                    committed_lines_by_product[product_id] = committed_lines

            # R3: faltante acumulado cronológico — la disponibilidad de cada
            # producto es una sola foto (`computed_at`) que se consume una
            # única vez recorriendo sus períodos en orden, no una copia
            # repetida en cada semana/mes (ver DECISION_LOG.md).
            #
            # V2 C: lo comprometido (V2 C) se consume igual de una sola vez,
            # pero DESPUÉS del faltante de stock — sólo cubre lo que el stock
            # no alcanzó a cubrir. En `forecasted` no se descuenta: Odoo ya
            # lo incluye dentro de `virtual_available` (evita doble cuenta).
            by_product = defaultdict(list)
            for data in buckets.values():
                by_product[data["product_id"]].append(data)
            for product_id, rows in by_product.items():
                rows.sort(key=lambda d: (d["period_index"], d["period_key"]))
                uom_id = rows[0]["uom_id"]
                rounding = (
                    self.env["uom.uom"].browse(uom_id).rounding
                    if uom_id else 0.0001
                )
                remaining_stock = availability_by_product[product_id]
                remaining_committed = (
                    0.0 if requirement.availability_metric == "forecasted"
                    else committed_by_product[product_id]
                )
                for data in rows:
                    total = data["budget_quantity"] + data["program_quantity"]
                    usable_stock = (
                        remaining_stock
                        if float_compare(remaining_stock, 0.0, precision_rounding=rounding) > 0
                        else 0.0
                    )
                    consumed_stock = min(total, usable_stock)
                    shortage = float_round(total - consumed_stock, precision_rounding=rounding)
                    shortage = max(shortage, 0.0)
                    remaining_stock = float_round(
                        remaining_stock - consumed_stock, precision_rounding=rounding
                    )

                    usable_committed = (
                        remaining_committed
                        if float_compare(remaining_committed, 0.0, precision_rounding=rounding) > 0
                        else 0.0
                    )
                    consumed_committed = min(shortage, usable_committed)
                    net = float_round(shortage - consumed_committed, precision_rounding=rounding)
                    remaining_committed = float_round(
                        remaining_committed - consumed_committed, precision_rounding=rounding
                    )

                    data["shortage_quantity"] = shortage
                    data["committed_quantity"] = committed_by_product[product_id]
                    data["net_to_buy"] = max(net, 0.0)

            commands = [
                (0, 0, {
                    "product_id": data["product_id"],
                    "uom_id": data["uom_id"],
                    "period_key": data["period_key"],
                    "period_label": data["period_label"],
                    "period_index": data["period_index"],
                    "budget_quantity": data["budget_quantity"],
                    "program_quantity": data["program_quantity"],
                    "available_quantity": availability_by_product[data["product_id"]],
                    "shortage_quantity": data["shortage_quantity"],
                    "committed_quantity": data["committed_quantity"],
                    "net_to_buy": data["net_to_buy"],
                    "committed_purchase_line_ids": [
                        (6, 0, committed_lines_by_product[data["product_id"]].ids)
                    ],
                })
                for data in buckets.values()
            ]
            requirement.write({
                "line_ids": commands,
                "state": "computed",
                "computed_at": fields.Datetime.now(),
            })
            requirement.message_post(body=_(
                "Necesidades calculadas: %(lines)s línea(s) desde %(b)s "
                "presupuesto(s) y %(p)s programa(s). Disponibilidad "
                "(%(metric)s) leída al %(when)s."
            ) % {
                "lines": len(commands),
                "b": len(requirement._source_budgets()) if requirement.include_budgets else 0,
                "p": len(requirement._source_programs()) if requirement.include_programs else 0,
                "metric": dict(requirement._fields["availability_metric"].selection)[
                    requirement.availability_metric
                ],
                "when": requirement.computed_at,
            })
        return True

    def action_set_draft(self):
        self.write({"state": "draft"})


class StepManagementStockRequirementLine(models.Model):
    _name = "step.management.stock.requirement.line"
    _description = "Línea de necesidades de stock"
    _order = "requirement_id, product_id, period_index, period_key, id"
    _check_company_auto = True

    requirement_id = fields.Many2one(
        "step.management.stock.requirement", string="Necesidad", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="requirement_id.company_id", string="Empresa", store=True, index=True,
    )
    product_id = fields.Many2one("product.product", string="Producto", required=True, index=True)
    uom_id = fields.Many2one("uom.uom", string="UdM")
    period_key = fields.Char(string="Período", required=True, index=True)
    period_label = fields.Char(string="Período")
    period_index = fields.Integer(string="Orden", default=0)
    budget_quantity = fields.Float(string="Desde presupuesto", digits=(16, 4))
    program_quantity = fields.Float(string="Desde programas", digits=(16, 4))
    total_quantity = fields.Float(
        string="Total requerido", compute="_compute_total", store=True, digits=(16, 4),
    )
    available_quantity = fields.Float(
        string="Disponible", digits=(16, 4),
        help="Disponibilidad del producto (según la métrica del encabezado) "
             "al instante de «Calcular». Es la misma para todos los "
             "períodos del producto — no varía por semana/mes.",
    )
    shortage_quantity = fields.Float(
        string="Faltante acumulado", digits=(16, 4),
        help="R3: faltante acumulado del producto hasta este período, "
             "consumiendo la disponibilidad una sola vez en orden "
             "cronológico. No es `total - disponible` de esta línea aislada "
             "— dos períodos no pueden descontar la misma disponibilidad. "
             "Se fija en `action_compute()`, junto con `available_quantity`.",
    )
    committed_quantity = fields.Float(
        string="Comprometido", digits=(16, 4),
        help="V2 C: cantidad pendiente de facturar en órdenes de compra "
             "confirmadas (`purchase.order.state = 'purchase'`). Es la "
             "misma foto para todos los períodos del producto, igual que "
             "`available_quantity` — nunca se cuenta dos veces en distintas "
             "semanas/meses.",
    )
    net_to_buy = fields.Float(
        string="Neto por comprar", digits=(16, 4),
        help="Faltante acumulado menos lo comprometido, consumiendo ambos "
             "una sola vez y en ese orden (primero stock, después lo "
             "comprometido). Con la métrica «Pronosticada» no se descuenta "
             "lo comprometido de nuevo: `virtual_available` ya lo incluye.",
    )
    committed_purchase_line_ids = fields.Many2many(
        "purchase.order.line", string="Líneas de compra comprometidas",
        help="Trazabilidad: líneas de OC confirmadas y no facturadas por "
             "completo que componen `committed_quantity` de este producto.",
    )

    _sql_constraints = [
        ("stock_requirement_line_unique",
         "unique(requirement_id, product_id, period_key)",
         "No puede repetirse el mismo producto y período en una necesidad de stock."),
    ]

    @api.depends("budget_quantity", "program_quantity")
    def _compute_total(self):
        for line in self:
            line.total_quantity = line.budget_quantity + line.program_quantity
