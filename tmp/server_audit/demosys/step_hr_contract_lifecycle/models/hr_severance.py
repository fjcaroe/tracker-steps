# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .hr_severance_calc import (
    compute_feriado_proporcional,
    compute_ias_anual,
    compute_ias_mensual,
    compute_mes_aviso,
)

HABERES_FIELDS = [
    "gratificacion", "bonos", "horas_extraordinarias", "aguinaldo",
    "semana_corrida", "comision", "movilizacion", "colacion",
    "perdida_caja", "desgaste_herramientas", "viaticos",
    "asignaciones_familiares", "remuneracion_pendiente",
]
DESCUENTOS_FIELDS = [
    "descuento_seguridad_social", "descuento_impuestos", "descuento_afc",
    "descuento_anticipos", "descuento_indemnizacion_anticipada",
    "descuento_pension_alimenticia", "descuento_caja_compensacion",
    "descuento_prestamos", "descuento_anticipo_sueldo",
    "descuento_vacaciones_anticipadas",
]


class HrSeverance(models.Model):
    """Finiquito. Flujo auditable:
    Borrador -> Prevalidación -> Cálculo -> Revisión -> Aprobación ->
    Documento emitido -> Firma/aceptación -> Pago -> Contabilizado ->
    Cerrado, con estados alternativos Observado/Rechazado/Cancelado/
    Reabierto, todos con motivo, responsable y fecha.

    NO usa los factores de costo agrícola de step_hr (SIS, aporte
    patronal, etc.): esos son para provisión de costos, no para el
    cálculo legal del finiquito."""

    _name = "hr.severance"
    _description = "Finiquito de contrato de trabajo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    contract_id = fields.Many2one("hr.contract", required=True, tracking=True)
    employee_id = fields.Many2one(related="contract_id.employee_id", store=True)
    notice_id = fields.Many2one("hr.termination.notice", string="Aviso de término")
    causal_id = fields.Many2one("hr.causal.termino", required=True, tracking=True)
    date_termino = fields.Date(required=True, tracking=True)
    currency_id = fields.Many2one(related="company_id.currency_id")

    income_type = fields.Selection(
        [("fija", "Renta fija"), ("variable", "Renta variable"), ("mixta", "Renta mixta")],
        required=True,
        default="fija",
        tracking=True,
    )
    last_payslip_ids = fields.Many2many(
        "hr.payslip",
        string="Liquidaciones usadas (últimos 3 meses)",
        help="Para renta variable/mixta: liquidaciones cuyo promedio se "
        "usa como base. Debe quedar visible cuáles se usaron.",
    )
    renta_base = fields.Monetary(
        string="Renta base para feriado/IAS",
        help="Sueldo fijo, o promedio de los últimos 3 meses si es "
        "variable/mixta. Editable con motivo (ajuste manual).",
        tracking=True,
    )
    manual_adjustment_reason = fields.Char(string="Motivo de ajuste manual")

    uf_value = fields.Float(string="Valor UF usado")
    uf_date = fields.Date(string="Fecha UF")
    uf_source = fields.Char(string="Fuente UF", help="Ej: sbif.cl, Banco Central.")

    # -- Feriado proporcional --------------------------------------------------
    feriado_dias_habiles = fields.Float(readonly=True)
    feriado_dias_finales = fields.Float(readonly=True)
    feriado_window_start = fields.Date(readonly=True)
    feriado_window_end = fields.Date(readonly=True)
    feriado_amount = fields.Monetary(readonly=True, tracking=True)

    # -- IAS anual --------------------------------------------------------------
    ias_anual_years = fields.Integer(readonly=True)
    ias_anual_applies = fields.Boolean(readonly=True)
    ias_anual_tope_uf_aplicado = fields.Boolean(readonly=True)
    ias_anual_amount = fields.Monetary(readonly=True, tracking=True)

    # -- IAS mensual --------------------------------------------------------------
    ias_mensual_months = fields.Integer(readonly=True)
    ias_mensual_applies = fields.Boolean(readonly=True)
    ias_mensual_amount = fields.Monetary(readonly=True, tracking=True)

    # -- Mes de aviso --------------------------------------------------------------
    mes_aviso_amount = fields.Monetary(readonly=True, tracking=True)

    # -- Otros haberes / descuentos (ingreso manual, referenciados a la liquidación) --
    gratificacion = fields.Monetary()
    bonos = fields.Monetary()
    horas_extraordinarias = fields.Monetary()
    aguinaldo = fields.Monetary()
    semana_corrida = fields.Monetary()
    comision = fields.Monetary()
    movilizacion = fields.Monetary()
    colacion = fields.Monetary()
    perdida_caja = fields.Monetary()
    desgaste_herramientas = fields.Monetary()
    viaticos = fields.Monetary()
    asignaciones_familiares = fields.Monetary()
    remuneracion_pendiente = fields.Monetary()

    descuento_seguridad_social = fields.Monetary()
    descuento_impuestos = fields.Monetary()
    descuento_afc = fields.Monetary()
    descuento_anticipos = fields.Monetary()
    descuento_indemnizacion_anticipada = fields.Monetary()
    descuento_pension_alimenticia = fields.Monetary()
    descuento_caja_compensacion = fields.Monetary()
    descuento_prestamos = fields.Monetary()
    descuento_anticipo_sueldo = fields.Monetary()
    descuento_vacaciones_anticipadas = fields.Monetary()

    retencion_alimentos = fields.Boolean(
        string="Retención de alimentos (Ley 21.389)"
    )
    retencion_alimentos_notes = fields.Text()

    total_indemnizaciones = fields.Monetary(compute="_compute_totals", store=True)
    total_haberes = fields.Monetary(compute="_compute_totals", store=True)
    total_descuentos = fields.Monetary(compute="_compute_totals", store=True)
    total_a_pagar = fields.Monetary(compute="_compute_totals", store=True, tracking=True)

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("prevalidated", "Prevalidación"),
            ("calculated", "Cálculo"),
            ("review", "Revisión"),
            ("approved", "Aprobación"),
            ("document_issued", "Documento emitido"),
            ("signed", "Firma/aceptación"),
            ("paid", "Pago"),
            ("accounted", "Contabilizado"),
            ("closed", "Cerrado"),
            ("observed", "Observado"),
            ("rejected", "Rechazado"),
            ("cancelled", "Cancelado"),
            ("reopened", "Reabierto"),
        ],
        default="draft",
        tracking=True,
    )
    state_reason = fields.Text(string="Motivo del estado")
    responsible_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_date = fields.Datetime(readonly=True)
    document_id = fields.Many2one("hr.labor.document", readonly=True)
    account_move_id = fields.Many2one("account.move", readonly=True, string="Asiento contable")
    payment_id = fields.Many2one("account.payment", readonly=True)

    @api.depends(
        "feriado_amount", "ias_anual_amount", "ias_mensual_amount", "mes_aviso_amount",
        *HABERES_FIELDS, *DESCUENTOS_FIELDS,
    )
    def _compute_totals(self):
        for sev in self:
            sev.total_indemnizaciones = (
                sev.feriado_amount + sev.ias_anual_amount + sev.ias_mensual_amount
                + sev.mes_aviso_amount
            )
            sev.total_haberes = sum(sev[f] for f in HABERES_FIELDS)
            sev.total_descuentos = sum(sev[f] for f in DESCUENTOS_FIELDS)
            sev.total_a_pagar = (
                sev.total_indemnizaciones + sev.total_haberes - sev.total_descuentos
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("hr.severance") or _("Nuevo")
        return super().create(vals_list)

    def action_prevalidate(self):
        for sev in self:
            existing = self.search(
                [
                    ("contract_id", "=", sev.contract_id.id),
                    ("id", "!=", sev.id),
                    ("state", "not in", ("cancelled", "rejected")),
                ]
            )
            if existing:
                raise UserError(
                    _("Ya existe un proceso de finiquito abierto para este contrato.")
                )
            if not sev.date_termino or not sev.causal_id:
                raise UserError(_("Falta fecha de término o causal."))
            if sev.income_type != "fija" and not sev.last_payslip_ids:
                raise UserError(
                    _(
                        "Para renta variable/mixta debe indicar las "
                        "liquidaciones de los últimos 3 meses usadas."
                    )
                )
            sev.state = "prevalidated"

    def action_calculate(self):
        for sev in self:
            if sev.state != "prevalidated":
                raise UserError(_("Prevalide antes de calcular."))
            contract = sev.contract_id
            date_from = contract.date_start
            renta_base = sev.renta_base or contract.wage
            daily_wage = round((renta_base or 0) / 30, 2)

            holidays = set()
            leaves = self.env["resource.calendar.leaves"].search(
                [
                    ("calendar_id", "=", contract.resource_calendar_id.id),
                    ("resource_id", "=", False),
                ]
            )
            for leave in leaves:
                d = leave.date_from.date() if leave.date_from else False
                d_end = leave.date_to.date() if leave.date_to else d
                if d:
                    cur = d
                    while cur <= d_end:
                        holidays.add(cur)
                        cur += timedelta(days=1)

            feriado = compute_feriado_proporcional(
                date_from, sev.date_termino, daily_wage, frozenset(holidays)
            )
            vals = {
                "renta_base": renta_base,
                "feriado_dias_habiles": feriado["dias_habiles_entitled"],
                "feriado_dias_finales": feriado["final_days"],
                "feriado_window_start": feriado["window_start"],
                "feriado_window_end": feriado["window_end"],
                "feriado_amount": feriado["amount"],
            }
            if sev.causal_id.applies_ias_anual:
                ias_a = compute_ias_anual(date_from, sev.date_termino, renta_base, sev.uf_value)
                vals.update(
                    {
                        "ias_anual_years": ias_a["anios_ias"],
                        "ias_anual_applies": ias_a["applies"],
                        "ias_anual_tope_uf_aplicado": ias_a["tope_uf_aplicado"],
                        "ias_anual_amount": ias_a["amount"],
                    }
                )
            if sev.causal_id.applies_ias_mensual:
                ias_m = compute_ias_mensual(date_from, sev.date_termino, renta_base)
                vals.update(
                    {
                        "ias_mensual_months": ias_m["meses_ias"],
                        "ias_mensual_applies": ias_m["applies"],
                        "ias_mensual_amount": ias_m["amount"],
                    }
                )
            if sev.causal_id.applies_mes_aviso:
                mes_aviso = compute_mes_aviso(renta_base)
                vals["mes_aviso_amount"] = mes_aviso["amount"]
            sev.write(vals)
            sev.state = "calculated"

    def action_send_review(self):
        self.write({"state": "review"})

    def action_approve(self):
        if not self.env.user.has_group(
            "step_hr_contract_lifecycle.group_severance_approve"
        ):
            raise UserError(_("No tiene el permiso de aprobación de finiquitos."))
        for sev in self:
            if sev.state != "review":
                raise UserError(_("El finiquito debe estar en revisión para aprobarse."))
            sev.write(
                {
                    "state": "approved",
                    "approved_by": self.env.user.id,
                    "approved_date": fields.Datetime.now(),
                }
            )

    def action_issue_document(self):
        self.ensure_one()
        template = self.env["hr.labor.template"].search(
            [
                ("document_type", "=", "severance"),
                ("company_id", "=", self.company_id.id),
                ("state", "=", "validated"),
            ],
            limit=1,
        )
        if not template:
            raise UserError(_("No hay una plantilla de finiquito validada."))
        doc = self.env["hr.labor.document"].generate_from_template(
            self.contract_id, template, "severance"
        )
        self.write({"document_id": doc.id, "state": "document_issued"})
        return doc

    def action_mark_signed(self):
        self.write({"state": "signed"})

    def action_mark_paid(self):
        self.write({"state": "paid"})

    def action_close(self):
        for sev in self:
            if sev.state != "accounted":
                raise UserError(_("Sólo se cierra un finiquito ya contabilizado."))
            sev.state = "closed"
            sev.contract_id.write({"state": "close"})

    def action_observe(self):
        for sev in self:
            if not sev.state_reason:
                raise UserError(_("Indique el motivo de la observación."))
            sev.state = "observed"

    def action_reject(self):
        for sev in self:
            if not sev.state_reason:
                raise UserError(_("Indique el motivo del rechazo."))
            sev.state = "rejected"

    def action_cancel(self):
        for sev in self:
            if not sev.state_reason:
                raise UserError(_("Indique el motivo de la cancelación."))
            sev.state = "cancelled"

    def action_create_dt_batches(self):
        approved = self.filtered(lambda s: s.state not in ("draft", "prevalidated"))
        if not approved:
            raise UserError(
                _("Calcule los finiquitos antes de generar el lote DT.")
            )
        batches = self.env["hr.severance.dt.batch"].create_batches_from_severances(approved)
        return {
            "type": "ir.actions.act_window",
            "name": _("Lotes DT generados"),
            "res_model": "hr.severance.dt.batch",
            "view_mode": "list,form",
            "domain": [("id", "in", batches.ids)],
        }

    def action_reopen(self):
        for sev in self:
            if not sev.state_reason:
                raise UserError(_("Indique el motivo de la reapertura."))
            if sev.state == "closed":
                raise UserError(
                    _(
                        "No se puede reabrir un finiquito ya cerrado desde aquí: "
                        "requiere un flujo controlado de reversa contable."
                    )
                )
            sev.state = "reopened"
