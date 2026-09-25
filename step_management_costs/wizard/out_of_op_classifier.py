"""Corte V2 F, punto 5 — clasificación de gasto real fuera de OP.

Clave pedida por el corte: centro + temporada + actividad + grupo
presupuestario. La dimensión **actividad** queda deliberadamente fuera de
esta primera versión: la única fuente técnica disponible para derivarla a
partir de un apunte contable real es `product.template.actividad_id` →
`account.analytic.account`, cuya semántica es exactamente D20 — uno de los
bloqueos permanentes ya documentados (`DECISION_LOG.md`). Se aísla ese campo
y se continúa con las tres dimensiones que sí son demostrables (centro,
temporada derivada de la fecha del apunte, grupo presupuestario vía
`product_id._get_management_budget_group()`, ya usado por el núcleo). Cuando
D20 se resuelva, agregar la dimensión de actividad es una extensión de
`_bucket_key`, no un rediseño.

No excluye ni mezcla: cada bucket queda marcado `backed_by_op` (bool) y
`op_names` (folios de las OP que lo amparan, vacío si ninguna); ambos casos
se muestran juntos, ordenados, nunca ocultos.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StepManagementOutOfOpWizard(models.TransientModel):
    _name = "step.management.out.of.op.wizard"
    _description = "Gasto real dentro / fuera de OP"

    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)
    only_out_of_op = fields.Boolean(string="Sólo fuera de OP")
    computed = fields.Boolean(default=False)
    line_ids = fields.One2many("step.management.out.of.op.line", "wizard_id", string="Detalle")
    total_in_op = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_out_of_op = fields.Monetary(compute="_compute_totals", currency_field="currency_id")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha «Desde» no puede ser posterior a «Hasta»."))

    @api.depends("line_ids.amount", "line_ids.backed_by_op")
    def _compute_totals(self):
        for wiz in self:
            wiz.total_in_op = sum(wiz.line_ids.filtered("backed_by_op").mapped("amount"))
            wiz.total_out_of_op = sum(
                wiz.line_ids.filtered(lambda l: not l.backed_by_op).mapped("amount")
            )

    def _read_real_cost_buckets(self):
        """Lee apuntes contables publicados de gasto (`account_type`
        `expense*`), igual criterio que `_read_analytic_actuals` (A1-A3 en
        `analytic_actuals.py`), pero sin acotarse a un presupuesto: recorre
        todos los centros con cuenta analítica de la empresa. Agrupa por
        (centro, temporada derivada de la fecha, grupo)."""
        self.ensure_one()
        centers = self.env["step.management.cost.center"].search([
            ("company_id", "=", self.company_id.id), ("analytic_account_id", "!=", False),
        ])
        # `account_to_center_map()` exige 1 cuenta analítica = 1 centro y
        # levanta `UserError` si dos centros la comparten — nunca atribuye
        # en silencio al que gane una colisión de iteración (ver
        # `cost_center.py::account_to_center_map`).
        account_to_center = centers.account_to_center_map()
        if not account_to_center:
            return {}
        move_lines = self.env["account.move.line"].search([
            ("parent_state", "=", "posted"),
            ("date", ">=", self.date_from), ("date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
            ("display_type", "in", ("product", False)),
        ])
        period = self.env["step.management.period.service"]
        buckets = {}
        for mline in move_lines:
            if not mline.analytic_distribution:
                continue
            account_type = mline.account_id.account_type or ""
            if not account_type.startswith("expense"):
                continue  # sólo gasto: "fuera de OP" no aplica a ingresos
            pct_for_center = {}
            for raw_key, pct in (mline.analytic_distribution or {}).items():
                for token in str(raw_key).split(","):
                    try:
                        acc_id = int(token)
                    except (TypeError, ValueError):
                        continue
                    if acc_id in account_to_center:
                        pct_for_center[acc_id] = pct_for_center.get(acc_id, 0.0) + pct
            if not pct_for_center:
                continue
            group = (
                mline.product_id._get_management_budget_group(self.company_id)
                if mline.product_id else False
            )
            season = period.season_of_date(mline.date)
            for acc_id, pct in pct_for_center.items():
                center = account_to_center[acc_id]
                amount = mline.balance * (pct / 100.0)
                key = (center.id, season, group.id if group else False)
                bucket = buckets.setdefault(key, {
                    "center_id": center.id, "season": season,
                    "group_id": group.id if group else False,
                    "amount": 0.0, "move_line_ids": self.env["account.move.line"],
                })
                bucket["amount"] += amount
                bucket["move_line_ids"] |= mline
        return buckets

    def _op_coverage(self, center_id, season, group_id):
        """Folios de OP autorizadas/reemplazadas que amparan (centro,
        temporada, grupo) — al menos una línea con ese `budget_group_id`."""
        domain = [
            ("center_id", "=", center_id), ("season", "=", season),
            ("state", "in", ("authorized", "superseded")),
        ]
        if group_id:
            domain.append(("line_ids.budget_group_id", "=", group_id))
        else:
            domain.append(("line_ids.budget_group_id", "=", False))
        orders = self.env["step.management.production.order"].search(domain)
        return orders

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        buckets = self._read_real_cost_buckets()
        commands = []
        for (center_id, season, group_id), bucket in buckets.items():
            orders = self._op_coverage(center_id, season, group_id)
            if self.only_out_of_op and orders:
                continue
            commands.append((0, 0, {
                "center_id": center_id, "season": season, "group_id": group_id,
                "amount": bucket["amount"],
                "backed_by_op": bool(orders),
                "op_names": ", ".join(orders.mapped("name")),
                "move_line_ids": [(6, 0, bucket["move_line_ids"].ids)],
            }))
        self.write({"line_ids": commands, "computed": True})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class StepManagementOutOfOpLine(models.TransientModel):
    _name = "step.management.out.of.op.line"
    _description = "Línea de gasto real dentro / fuera de OP"
    _order = "backed_by_op, amount desc"

    wizard_id = fields.Many2one(
        "step.management.out.of.op.wizard", required=True, ondelete="cascade",
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    center_id = fields.Many2one("step.management.cost.center", string="Centro")
    season = fields.Char(string="Temporada")
    group_id = fields.Many2one("step.management.budget.group", string="Grupo")
    group_label = fields.Char(compute="_compute_group_label", string="Grupo")
    amount = fields.Monetary(string="Monto real", currency_field="currency_id")
    backed_by_op = fields.Boolean(string="Amparado por OP")
    op_names = fields.Char(string="OP")
    source_label = fields.Char(
        compute="_compute_source_label", string="Procedencia",
        help="Punto 6 del corte: el folio real de la OP cuando existe; si "
             "no, la semana ISO derivada de la fecha de los apuntes "
             "(«Wxx/AAAA (derivado)») — nunca un folio inventado.",
    )
    move_line_ids = fields.Many2many("account.move.line", string="Apuntes")
    move_count = fields.Integer(compute="_compute_move_count")

    @api.depends("group_id")
    def _compute_group_label(self):
        for line in self:
            line.group_label = line.group_id.display_name or _("Sin clasificar")

    @api.depends("backed_by_op", "op_names", "move_line_ids.date")
    def _compute_source_label(self):
        period = self.env["step.management.period.service"]
        for line in self:
            if line.backed_by_op:
                line.source_label = line.op_names
                continue
            dates = line.move_line_ids.mapped("date")
            if not dates:
                line.source_label = _("Sin origen registrado")
                continue
            weeks = sorted({
                "W%02d/%s" % (w["iso_week"], w["iso_year"])
                for a_date in dates
                for w in period.iso_weeks(a_date, a_date)
            })
            line.source_label = _("%s (derivado)") % ", ".join(weeks) if weeks else _(
                "Sin origen registrado"
            )

    @api.depends("move_line_ids")
    def _compute_move_count(self):
        for line in self:
            line.move_count = len(line.move_line_ids)

    def action_open_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Apuntes contables"),
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("id", "in", self.move_line_ids.ids)],
            "target": "current",
        }
