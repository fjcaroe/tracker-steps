# -*- coding: utf-8 -*-
"""Dataset canónico del flujo de caja.

Todas las hojas, el resumen, los KPI y las exportaciones se derivan de este
único modelo. No hay una segunda fuente de cifras.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .treasury_concept import INFLOW_SHEETS, OUTFLOW_SHEETS, SHEET_SELECTION

#: Cubetas del horizonte. `w1`..`w5` son ventanas de siete días desde el inicio.
BUCKET_SELECTION = [
    ("overdue", "Vencido"),
    ("w1", "W1"),
    ("w2", "W2"),
    ("w3", "W3"),
    ("w4", "W4"),
    ("w5", "W5"),
    ("other", "Otros"),
]

BUCKET_CODES = [code for code, _label in BUCKET_SELECTION]

#: Días que cubre el horizonte: cinco semanas de siete días.
HORIZON_DAYS = 35


class StepCashflowLine(models.Model):
    _name = "step.cashflow.line"
    _description = "Línea de flujo de caja"
    _order = "cashflow_id, sheet, due_date, id"
    _check_company_auto = True

    cashflow_id = fields.Many2one(
        "step.cashflow", string="Flujo", required=True, ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(related="cashflow_id.company_id", store=True, index=True)
    state = fields.Selection(related="cashflow_id.state", store=True, index=True)
    sheet = fields.Selection(SHEET_SELECTION, string="Hoja", required=True, index=True)
    flow_type = fields.Selection(
        [("inflow", "Ingreso"), ("outflow", "Egreso")],
        string="Signo", compute="_compute_flow_type", store=True, index=True,
    )
    concept_id = fields.Many2one(
        "step.treasury.concept", string="Concepto de flujo", check_company=True, index=True,
    )

    # --- documento de origen ------------------------------------------------
    source_model = fields.Char(string="Modelo origen", index=True, readonly=True)
    source_id = fields.Integer(string="Id origen", index=True, readonly=True)
    source_line_id = fields.Integer(string="Id línea origen", readonly=True, default=0)
    is_manual = fields.Boolean(
        string="Manual", default=False, index=True,
        help="Las líneas manuales no se tocan al actualizar datos.",
    )

    # --- identificación del documento --------------------------------------
    partner_id = fields.Many2one("res.partner", string="Nombre", index=True)
    partner_vat = fields.Char(string="RUT")
    doc_type_id = fields.Many2one("l10n_latam.document.type", string="Tipo Doc")
    doc_type_name = fields.Char(string="Tipo documento")
    doc_number = fields.Char(string="Num Doc")
    doc_date = fields.Date(string="Fecha Doc")
    due_date = fields.Date(string="Vencimiento", index=True)

    # --- importes -----------------------------------------------------------
    currency_id = fields.Many2one("res.currency", string="Moneda Doc", required=True)
    amount_origin = fields.Monetary(
        string="Saldo Docto", currency_field="currency_id",
        help="Importe en la moneda del documento, tal como está en Odoo.",
    )
    flow_currency_id = fields.Many2one(
        related="cashflow_id.currency_id", string="Moneda del flujo", store=True,
    )
    amount_flow = fields.Monetary(
        string="Importe", currency_field="flow_currency_id",
        compute="_compute_amount_flow", store=True, readonly=False,
    )
    aux_currency_id = fields.Many2one(
        related="cashflow_id.aux_currency_id", string="Moneda auxiliar", store=True,
    )
    amount_aux = fields.Monetary(
        string="Total auxiliar", currency_field="aux_currency_id",
        compute="_compute_amount_flow", store=True,
    )

    # --- clasificación temporal --------------------------------------------
    bucket = fields.Selection(
        BUCKET_SELECTION, string="Cubeta", compute="_compute_bucket", store=True, index=True,
    )
    bucket_label = fields.Char(
        string="Semana", compute="_compute_bucket_label", store=True,
        help="La cubeta con la semana calendario real del horizonte: W35, W36, …",
    )
    amount_overdue = fields.Monetary(string="Vencido", currency_field="flow_currency_id", compute="_compute_bucket_amounts")
    amount_w1 = fields.Monetary(string="W1", currency_field="flow_currency_id", compute="_compute_bucket_amounts")
    amount_w2 = fields.Monetary(string="W2", currency_field="flow_currency_id", compute="_compute_bucket_amounts")
    amount_w3 = fields.Monetary(string="W3", currency_field="flow_currency_id", compute="_compute_bucket_amounts")
    amount_w4 = fields.Monetary(string="W4", currency_field="flow_currency_id", compute="_compute_bucket_amounts")
    amount_w5 = fields.Monetary(string="W5", currency_field="flow_currency_id", compute="_compute_bucket_amounts")
    amount_other = fields.Monetary(string="Otros", currency_field="flow_currency_id", compute="_compute_bucket_amounts")

    # --- gestión ------------------------------------------------------------
    excluded = fields.Boolean(
        string="Excluir", default=False,
        help="La línea se conserva pero no suma en el resumen.",
    )
    comment = fields.Char(string="Comentario")
    adjust_reason = fields.Char(string="Motivo de ajuste")

    _sql_constraints = [
        ("source_uniq",
         "unique(cashflow_id, source_model, source_id, source_line_id)",
         "El mismo documento origen ya está en este flujo."),
    ]

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends("sheet")
    def _compute_flow_type(self):
        for line in self:
            if line.sheet in INFLOW_SHEETS:
                line.flow_type = "inflow"
            elif line.sheet in OUTFLOW_SHEETS:
                line.flow_type = "outflow"
            else:
                line.flow_type = False

    @api.depends("amount_origin", "currency_id", "cashflow_id.currency_id",
                 "cashflow_id.aux_currency_id", "cashflow_id.rate_date",
                 "cashflow_id.applied_rate", "cashflow_id.aux_applied_rate")
    def _compute_amount_flow(self):
        for line in self:
            flow = line.cashflow_id
            line.amount_flow = flow._convert_to_flow(line.amount_origin, line.currency_id)
            line.amount_aux = flow._convert_to_aux(line.amount_origin, line.currency_id)

    @api.depends("due_date", "cashflow_id.start_date", "cashflow_id.undated_policy")
    def _compute_bucket(self):
        for line in self:
            line.bucket = line.cashflow_id._bucket_for_date(line.due_date)

    @api.depends("bucket", "cashflow_id.start_date")
    def _compute_bucket_label(self):
        # Los rótulos dependen del horizonte, así que se resuelven por flujo y
        # no línea a línea: un flujo con mil líneas hace un solo cálculo.
        for flow, lines in self.grouped("cashflow_id").items():
            labels = flow._bucket_labels() if flow else dict(BUCKET_SELECTION)
            for line in lines:
                line.bucket_label = labels.get(line.bucket) or ""

    @api.depends("bucket", "amount_flow", "excluded")
    def _compute_bucket_amounts(self):
        for line in self:
            amount = 0.0 if line.excluded else line.amount_flow
            for code in BUCKET_CODES:
                field = "amount_overdue" if code == "overdue" else "amount_%s" % code
                line[field] = amount if line.bucket == code else 0.0

    # ------------------------------------------------------------------
    # Restricciones
    # ------------------------------------------------------------------
    def _check_parent_snapshot_unlocked(self, operation):
        if self.env.context.get("treasury_bypass_lock"):
            return
        approved = self.mapped("cashflow_id").filtered(lambda flow: flow.state == "approved")
        if approved:
            raise UserError(_(
                "El flujo %s está aprobado: reábralo para %s sus líneas.")
                % (approved[0].display_name, operation))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("treasury_bypass_lock"):
            flow_ids = {vals.get("cashflow_id") for vals in vals_list if vals.get("cashflow_id")}
            approved = self.env["step.cashflow"].browse(flow_ids).filtered(
                lambda flow: flow.state == "approved")
            if approved:
                raise UserError(_(
                    "El flujo %s está aprobado: reábralo para agregar líneas.")
                    % approved[0].display_name)
        return super().create(vals_list)

    def write(self, vals):
        self._check_parent_snapshot_unlocked(_("modificar"))
        result = super().write(vals)
        # También impide mover una línea desde un flujo editable hacia uno aprobado.
        if "cashflow_id" in vals:
            self._check_parent_snapshot_unlocked(_("modificar"))
        return result

    def unlink(self):
        self._check_parent_snapshot_unlocked(_("eliminar"))
        return super().unlink()

    @api.constrains("concept_id", "company_id")
    def _check_concept_company(self):
        for line in self.filtered("concept_id"):
            if line.concept_id.company_id != line.company_id:
                raise ValidationError(_("El concepto pertenece a otra empresa."))

    def action_open_source(self):
        """Drill-down al documento Odoo de origen."""
        self.ensure_one()
        if not self.source_model or not self.source_id:
            return False
        if self.source_model not in self.env:
            return False
        record = self.env[self.source_model].browse(self.source_id).exists()
        if not record:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.source_model,
            "res_id": self.source_id,
            "view_mode": "form",
            "target": "current",
        }
