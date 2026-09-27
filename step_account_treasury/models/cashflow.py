# -*- coding: utf-8 -*-
"""Flujo de caja: encabezado, recolección de datos y resumen acumulado."""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

from .cashflow_line import BUCKET_CODES, BUCKET_SELECTION, HORIZON_DAYS
from .treasury_concept import INFLOW_SHEETS, OUTFLOW_SHEETS, SHEET_SELECTION

_logger = logging.getLogger(__name__)

#: Hojas alimentadas automáticamente desde documentos de Odoo.
AUTOMATIC_SHEETS = ("customer", "sale_order", "vendor", "purchase_order", "proforma")

#: Hojas exclusivamente manuales.
MANUAL_SHEETS = ("other_income", "other_payment")


class StepCashflow(models.Model):
    _name = "step.cashflow"
    _description = "Flujo de caja"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Nombre", required=True, copy=False, index=True,
        default=lambda self: _("Nuevo"), tracking=True,
    )
    date = fields.Datetime(
        string="Fecha", required=True, default=fields.Datetime.now, tracking=True,
        help="Fecha y hora en que se construye el flujo.",
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, index=True,
        default=lambda self: self.env.company, tracking=True,
    )
    start_date = fields.Date(
        string="Inicio del horizonte", required=True, tracking=True,
        default=fields.Date.context_today,
    )
    end_date = fields.Date(
        string="Fin del horizonte", compute="_compute_end_date", store=True,
        help="Cinco semanas de siete días: inicio + 34 días, ambos inclusive.",
    )
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", tracking=True,
        default=lambda self: self.env.user,
    )
    approver_id = fields.Many2one("res.users", string="Aprueba", tracking=True)
    currency_id = fields.Many2one(
        "res.currency", string="Moneda del flujo", required=True, tracking=True,
        default=lambda self: self.env.company.currency_id,
    )
    aux_currency_id = fields.Many2one(
        "res.currency", string="Moneda auxiliar", tracking=True,
        default=lambda self: self.env.company.operational_currency_id,
        help="Segunda columna de presentación. Por omisión, la moneda operativa "
             "configurada en Contabilidad Multimoneda.",
    )
    rate_policy = fields.Selection(
        [("odoo", "Tasas de Odoo a la fecha de conversión"),
         ("manual", "Tipo de cambio manual")],
        string="Política de tipo de cambio", default="odoo", required=True, tracking=True,
    )
    rate_date = fields.Date(
        string="Fecha de conversión", tracking=True,
        help="Fecha con la que se leen las tasas de Odoo. Por omisión, el inicio del horizonte.",
    )
    manual_rate = fields.Float(
        string="Tipo de cambio", digits=(16, 6), tracking=True,
        help="Unidades de la moneda del flujo por cada unidad de la moneda auxiliar.",
    )
    manual_rate_reason = fields.Char(string="Motivo del tipo de cambio manual", tracking=True)
    manual_rate_uid = fields.Many2one("res.users", string="Tasa fijada por", readonly=True)
    manual_rate_date = fields.Datetime(string="Tasa fijada el", readonly=True)
    applied_rate = fields.Float(
        string="Tasa aplicada", digits=(16, 6), readonly=True, copy=False,
        help="Tasa congelada en el snapshot: moneda del flujo por unidad de moneda auxiliar.",
    )
    aux_applied_rate = fields.Float(
        string="Tasa auxiliar aplicada", digits=(16, 6), readonly=True, copy=False,
    )
    undated_policy = fields.Selection(
        [("other", "Clasificar en Otros"), ("w1", "Clasificar en W1")],
        string="Documentos sin vencimiento", default="other", required=True, tracking=True,
    )
    journal_ids = fields.Many2many(
        "account.journal", "step_cashflow_journal_rel", "cashflow_id", "journal_id",
        string="Diarios de banco y efectivo", check_company=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
    )
    state = fields.Selection(
        [("draft", "Nuevo"), ("in_progress", "En progreso"),
         ("approved", "Aprobado"), ("cancelled", "Anulado")],
        string="Estado", default="draft", required=True, tracking=True, index=True, copy=False,
    )
    line_ids = fields.One2many("step.cashflow.line", "cashflow_id", string="Detalle", copy=False)
    # Vistas por hoja sobre el MISMO dataset canónico: no son copias, son
    # dominios distintos sobre `line_ids`.
    line_customer_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Clientes",
        domain=[("sheet", "=", "customer")], context={"default_sheet": "customer"}, copy=False,
    )
    line_sale_order_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Notas de venta",
        domain=[("sheet", "=", "sale_order")], context={"default_sheet": "sale_order"}, copy=False,
    )
    line_other_income_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Otras recaudaciones",
        domain=[("sheet", "=", "other_income")], context={"default_sheet": "other_income"}, copy=False,
    )
    line_vendor_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Proveedores",
        domain=[("sheet", "=", "vendor")], context={"default_sheet": "vendor"}, copy=False,
    )
    line_purchase_order_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Órdenes de compra",
        domain=[("sheet", "=", "purchase_order")], context={"default_sheet": "purchase_order"}, copy=False,
    )
    line_proforma_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Proformas",
        domain=[("sheet", "=", "proforma")], context={"default_sheet": "proforma"}, copy=False,
    )
    line_other_payment_ids = fields.One2many(
        "step.cashflow.line", "cashflow_id", string="Otros pagos",
        domain=[("sheet", "=", "other_payment")], context={"default_sheet": "other_payment"}, copy=False,
    )
    opening_balance = fields.Monetary(
        string="Saldo inicial de banco", currency_field="currency_id",
        compute="_compute_opening_balance", store=True, readonly=False, copy=False,
    )
    total_inflow = fields.Monetary(string="Ingresos", currency_field="currency_id",
                                   compute="_compute_totals", store=True)
    total_outflow = fields.Monetary(string="Egresos", currency_field="currency_id",
                                    compute="_compute_totals", store=True)
    closing_balance = fields.Monetary(string="Saldo final", currency_field="currency_id",
                                      compute="_compute_totals", store=True)
    min_balance = fields.Monetary(string="Saldo mínimo proyectado", currency_field="currency_id",
                                  compute="_compute_totals", store=True)
    has_negative_cash = fields.Boolean(string="Alerta de caja negativa",
                                       compute="_compute_totals", store=True)
    line_count = fields.Integer(string="Líneas", compute="_compute_totals", store=True)
    approved_uid = fields.Many2one("res.users", string="Aprobado por", readonly=True, copy=False)
    approved_date = fields.Datetime(string="Aprobado el", readonly=True, copy=False)
    legacy_studio_id = fields.Integer(
        string="Id Studio de origen", readonly=True, copy=False, index=True,
    )

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)",
         "Ya existe un flujo con ese nombre en la empresa."),
    ]

    # ------------------------------------------------------------------
    # Horizonte y cubetas
    # ------------------------------------------------------------------
    @api.depends("start_date")
    def _compute_end_date(self):
        for flow in self:
            flow.end_date = flow.start_date + timedelta(days=HORIZON_DAYS - 1) if flow.start_date else False

    def _bucket_for_date(self, due_date):
        """Cubeta de una fecha de vencimiento según el horizonte del flujo."""
        self.ensure_one()
        if not self.start_date:
            return "other"
        if not due_date:
            return "w1" if self.undated_policy == "w1" else "other"
        if due_date < self.start_date:
            return "overdue"
        delta = (due_date - self.start_date).days
        if delta >= HORIZON_DAYS:
            return "other"
        return "w%d" % (delta // 7 + 1)

    def _bucket_bounds(self):
        """Límites de cada cubeta, para mostrarlos en la interfaz."""
        self.ensure_one()
        bounds = {}
        for index in range(5):
            start = self.start_date + timedelta(days=7 * index)
            bounds["w%d" % (index + 1)] = (start, start + timedelta(days=6))
        return bounds

    def _bucket_labels(self):
        """Etiquetas de las cubetas con la semana calendario real del horizonte.

        Internamente las cubetas siguen siendo `w1`..`w5` —ventanas de siete
        días desde el inicio—, pero quien lee el flujo piensa en la semana del
        calendario. Cada ventana se rotula con la semana ISO de su primer día,
        de modo que un horizonte que arranca el 25/08/2026 se lee W35, W36,
        W37, W38 y W39.

        Si el inicio no cae en lunes, la ventana cruza dos semanas ISO y manda
        la del primer día. Para que ventana y semana calendario coincidan
        exactamente, el horizonte debe empezar en lunes.
        """
        self.ensure_one()
        labels = dict(BUCKET_SELECTION)
        if not self.start_date:
            return labels
        for code, (start, _end) in self._bucket_bounds().items():
            labels[code] = "W%d" % start.isocalendar()[1]
        return labels

    def _bucket_label_hints(self):
        """Rango de fechas de cada cubeta, en formato dd/mm, para subtítulos."""
        self.ensure_one()
        if not self.start_date:
            return {}
        return {
            code: "%s – %s" % (start.strftime("%d/%m"), end.strftime("%d/%m"))
            for code, (start, end) in self._bucket_bounds().items()
        }

    # ------------------------------------------------------------------
    # Conversión de moneda
    # ------------------------------------------------------------------
    def _conversion_date(self):
        self.ensure_one()
        return self.rate_date or self.start_date or fields.Date.context_today(self)

    def _convert_to_flow(self, amount, from_currency):
        """Convierte un importe a la moneda del flujo respetando la política."""
        self.ensure_one()
        if not amount or not from_currency or not self.currency_id:
            return amount or 0.0
        if from_currency == self.currency_id:
            return amount
        rate = self.applied_rate or self.manual_rate
        if self.rate_policy == "manual" and rate and self.aux_currency_id \
                and from_currency == self.aux_currency_id:
            return self.currency_id.round(amount * rate)
        return from_currency._convert(
            amount, self.currency_id, self.company_id, self._conversion_date())

    def _convert_to_aux(self, amount, from_currency):
        """Convierte un importe a la moneda auxiliar de presentación."""
        self.ensure_one()
        if not self.aux_currency_id or not amount or not from_currency:
            return 0.0
        if from_currency == self.aux_currency_id:
            return amount
        rate = self.aux_applied_rate or self.applied_rate or self.manual_rate
        if self.rate_policy == "manual" and rate:
            in_flow = self._convert_to_flow(amount, from_currency)
            return self.aux_currency_id.round(in_flow / rate) if rate else 0.0
        return from_currency._convert(
            amount, self.aux_currency_id, self.company_id, self._conversion_date())

    def _freeze_rates(self):
        """Congela las tasas usadas para que el histórico no cambie."""
        for flow in self:
            if flow.rate_policy == "manual":
                rate = flow.manual_rate
            elif flow.aux_currency_id and flow.aux_currency_id != flow.currency_id:
                rate = flow.aux_currency_id._convert(
                    1.0, flow.currency_id, flow.company_id, flow._conversion_date())
            else:
                rate = 1.0
            flow.write({"applied_rate": rate, "aux_applied_rate": rate})
        return True

    @api.constrains("rate_policy", "manual_rate", "aux_currency_id")
    def _check_manual_rate(self):
        for flow in self:
            if flow.rate_policy != "manual":
                continue
            if not flow.aux_currency_id:
                raise ValidationError(_(
                    "Para usar un tipo de cambio manual defina la moneda auxiliar."))
            if flow.manual_rate <= 0:
                raise ValidationError(_("El tipo de cambio manual debe ser mayor que cero."))

    def write(self, vals):
        if "manual_rate" in vals:
            vals.setdefault("manual_rate_uid", self.env.user.id)
            vals.setdefault("manual_rate_date", fields.Datetime.now())
        # Un flujo aprobado es un snapshot financiero. La protección debe
        # existir en el ORM (RPC/importaciones incluidos), no sólo en la vista.
        # Se permiten únicamente metadatos técnicos de mail/adjuntos.
        approved_safe_fields = {
            "message_main_attachment_id", "message_follower_ids", "activity_ids",
        }
        financial_changes = set(vals) - approved_safe_fields
        if not self.env.context.get("treasury_bypass_lock") and financial_changes:
            for flow in self:
                if flow.state == "approved":
                    raise UserError(_(
                        "El flujo %s está aprobado. Reábralo para cambiar su base de cálculo.")
                        % flow.display_name)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Saldo inicial de banco
    # ------------------------------------------------------------------
    def _liquidity_accounts(self):
        self.ensure_one()
        journals = self.journal_ids or self.env["account.journal"].search([
            ("company_id", "=", self.company_id.id), ("type", "in", ("bank", "cash")),
        ])
        return journals, journals.mapped("default_account_id")

    @api.depends("journal_ids", "start_date", "company_id", "currency_id")
    def _compute_opening_balance(self):
        for flow in self:
            if flow.state == "approved":
                continue
            flow.opening_balance = sum(
                row["amount"] for row in flow._opening_balance_detail())

    def _opening_balance_detail(self):
        """Desglose del saldo de apertura por diario, cuenta y moneda.

        Corte explícito: sólo asientos publicados con fecha **anterior** al
        inicio del horizonte, para no contar dos veces los movimientos que el
        propio flujo proyecta el primer día.
        """
        self.ensure_one()
        if not self.start_date:
            return []
        journals, accounts = self._liquidity_accounts()
        if not accounts:
            return []
        lines = self.env["account.move.line"].search([
            ("company_id", "=", self.company_id.id),
            ("account_id", "in", accounts.ids),
            ("parent_state", "=", "posted"),
            ("date", "<", self.start_date),
        ])
        detail = {}
        for line in lines:
            key = (line.journal_id.id, line.account_id.id, line.currency_id.id)
            row = detail.setdefault(key, {
                "journal": line.journal_id.display_name,
                "account": line.account_id.display_name,
                "currency": line.currency_id.display_name,
                "balance": 0.0,
                "amount": 0.0,
            })
            row["balance"] += line.balance
        for row in detail.values():
            row["amount"] = self.company_id.currency_id._convert(
                row["balance"], self.currency_id, self.company_id, self._conversion_date())
        return list(detail.values())

    def action_open_opening_detail(self):
        """Drill-down contable del saldo inicial."""
        self.ensure_one()
        journals, accounts = self._liquidity_accounts()
        return {
            "type": "ir.actions.act_window",
            "name": _("Saldo inicial de banco"),
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("account_id", "in", accounts.ids),
                ("parent_state", "=", "posted"),
                ("date", "<", self.start_date),
            ],
            "context": {"search_default_group_by_account": 1},
        }

    # ------------------------------------------------------------------
    # Totales y resumen
    # ------------------------------------------------------------------
    @api.depends("line_ids.amount_flow", "line_ids.bucket", "line_ids.excluded",
                 "line_ids.flow_type", "opening_balance")
    def _compute_totals(self):
        for flow in self:
            summary = flow._summary_matrix()
            flow.total_inflow = sum(summary["inflow_total"].values())
            flow.total_outflow = sum(summary["outflow_total"].values())
            balances = [summary["closing"][code] for code in BUCKET_CODES]
            flow.closing_balance = balances[-1] if balances else flow.opening_balance
            flow.min_balance = min(balances) if balances else flow.opening_balance
            flow.has_negative_cash = any(
                value < 0 for value in balances) if balances else False
            flow.line_count = len(flow.line_ids)

    def _summary_matrix(self):
        """Matriz canónica del resumen: la única fuente de cifras agregadas."""
        self.ensure_one()
        zero = {code: 0.0 for code in BUCKET_CODES}
        by_sheet = {sheet: dict(zero) for sheet, _label in SHEET_SELECTION}
        by_sheet_aux = {sheet: dict(zero) for sheet, _label in SHEET_SELECTION}
        inflow_total, outflow_total = dict(zero), dict(zero)
        inflow_total_aux, outflow_total_aux = dict(zero), dict(zero)
        for line in self.line_ids:
            if line.excluded or not line.bucket:
                continue
            by_sheet[line.sheet][line.bucket] += line.amount_flow
            by_sheet_aux[line.sheet][line.bucket] += line.amount_aux
            if line.flow_type == "inflow":
                inflow_total[line.bucket] += line.amount_flow
                inflow_total_aux[line.bucket] += line.amount_aux
            elif line.flow_type == "outflow":
                outflow_total[line.bucket] += line.amount_flow
                outflow_total_aux[line.bucket] += line.amount_aux
        rate = self.applied_rate or self.manual_rate or 0.0
        opening_aux = (
            self.aux_currency_id.round(self.opening_balance / rate)
            if self.aux_currency_id and rate else 0.0
        )
        closing, previous = {}, self.opening_balance
        closing_aux, previous_aux = {}, opening_aux
        for code in BUCKET_CODES:
            previous = previous + inflow_total[code] - outflow_total[code]
            closing[code] = previous
            previous_aux = previous_aux + inflow_total_aux[code] - outflow_total_aux[code]
            closing_aux[code] = previous_aux
        return {
            "by_sheet": by_sheet,
            "by_sheet_aux": by_sheet_aux,
            "inflow_total": inflow_total,
            "inflow_total_aux": inflow_total_aux,
            "outflow_total": outflow_total,
            "outflow_total_aux": outflow_total_aux,
            "closing": closing,
            "closing_aux": closing_aux,
            "opening": self.opening_balance,
            "opening_aux": opening_aux,
        }

    def get_summary_rows(self):
        """Filas del resumen, en el orden del documento funcional."""
        self.ensure_one()
        matrix = self._summary_matrix()
        rows = [{
            "code": "opening", "label": _("Saldo Inicial Banco"), "kind": "opening",
            "buckets": {code: (matrix["opening"] if code == "overdue" else 0.0)
                        for code in BUCKET_CODES},
            "total": matrix["opening"], "total_aux": matrix["opening_aux"],
        }]
        for sheet, label in SHEET_SELECTION:
            values = matrix["by_sheet"][sheet]
            values_aux = matrix["by_sheet_aux"][sheet]
            total = sum(values.values())
            rows.append({
                "code": sheet, "label": label,
                "kind": "inflow" if sheet in INFLOW_SHEETS else "outflow",
                "buckets": values, "total": total, "total_aux": sum(values_aux.values()),
            })
            if sheet == "other_income":
                total_in = sum(matrix["inflow_total"].values())
                total_in_aux = sum(matrix["inflow_total_aux"].values())
                rows.append({
                    "code": "subtotal_in", "label": _("Sub total recaudaciones"), "kind": "subtotal",
                    "buckets": matrix["inflow_total"], "total": total_in,
                    "total_aux": total_in_aux,
                })
        total_out = sum(matrix["outflow_total"].values())
        total_out_aux = sum(matrix["outflow_total_aux"].values())
        rows.append({
            "code": "subtotal_out", "label": _("Sub total pagos"), "kind": "subtotal",
            "buckets": matrix["outflow_total"], "total": total_out,
            "total_aux": total_out_aux,
        })
        final = matrix["closing"][BUCKET_CODES[-1]]
        rows.append({
            "code": "closing", "label": _("Saldo Caja"), "kind": "closing",
            "buckets": matrix["closing"], "total": final,
            "total_aux": matrix["closing_aux"][BUCKET_CODES[-1]],
        })
        return rows

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nuevo"):
                company_id = vals.get("company_id") or self.env.company.id
                vals["name"] = self.env["ir.sequence"].with_company(company_id).next_by_code(
                    "step.cashflow") or _("Nuevo")
        flows = super().create(vals_list)
        flows._freeze_rates()
        return flows

    def action_start(self):
        self.filtered(lambda f: f.state == "draft").write({"state": "in_progress"})
        return True

    def action_approve(self):
        for flow in self:
            if flow.state != "in_progress":
                raise UserError(_("Sólo un flujo en progreso puede aprobarse."))
            if not flow.line_ids:
                raise UserError(_("Actualice los datos antes de aprobar el flujo."))
            if not self.env.user.has_group("step_account_treasury.group_treasury_approver"):
                raise UserError(_("Aprobar requiere el perfil Aprobador de Tesorería."))
            if flow.approver_id and flow.approver_id != self.env.user:
                raise UserError(_("Sólo el aprobador designado puede aprobar este flujo."))
        self._freeze_rates()
        self.write({
            "state": "approved",
            "approved_uid": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })
        for flow in self:
            flow.message_post(body=_("Flujo aprobado y snapshot financiero congelado."))
        return True

    def action_reopen(self):
        if not self.env.user.has_group("step_account_treasury.group_treasury_approver"):
            raise UserError(_("Reabrir un flujo aprobado requiere permiso de aprobación."))
        for flow in self:
            if flow.state != "approved":
                continue
            flow.with_context(treasury_bypass_lock=True).write({"state": "in_progress"})
            flow.message_post(body=_(
                "Flujo reabierto por %s. El snapshot deja de estar congelado.")
                % self.env.user.display_name)
        return True

    def action_cancel(self):
        self.filtered(lambda f: f.state != "approved").write({"state": "cancelled"})
        return True

    def action_draft(self):
        self.filtered(lambda f: f.state == "cancelled").write({"state": "draft"})
        return True
