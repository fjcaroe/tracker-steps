# -*- coding: utf-8 -*-
"""Corrección de finiquitos con la fecha real de término mal registrada.

Nació de un ticket real: un finiquito quedó con la asistencia validada y la
liquidación confirmada varias semanas después del último día trabajado. Nada
de eso era un error de código — es el comportamiento correcto de Odoo cuando
la fecha de término de un contrato no se actualiza a tiempo — pero corregirlo
a mano exige varios pasos técnicos que solo puede hacer un perfil con permiso
de Administrador, y un error de digitación en la fecha (día 7 vs día 8, por
ejemplo) es un error humano que va a volver a pasar.

Este wizard automatiza esos pasos con una vista previa antes de tocar nada:
- Corrige `date_end` del o los contratos abiertos que cubren esa fecha.
- Vuelve a borrador y elimina la asistencia validada posterior a esa fecha.
- Recalcula únicamente las liquidaciones abiertas afectadas.

Las liquidaciones validadas, pagadas o históricas bloquean la operación completa.
Requieren una corrección revisada por Nómina, conservando los importes originales.
"""

from datetime import datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_payroll_contracts.history import history_protected


class HrTerminationCorrectionWizard(models.TransientModel):
    _name = "hr.termination.correction.wizard"
    _description = "Corrección de asistencia y liquidación tras un finiquito"

    employee_id = fields.Many2one(
        "hr.employee", string="Trabajador", required=True,
        help="El trabajador cuyo finiquito quedó con una fecha de término incorrecta.",
    )
    company_id = fields.Many2one(related="employee_id.company_id", store=True)
    actual_termination_date = fields.Date(
        string="Último día realmente trabajado", required=True,
        help="La fecha correcta del finiquito. Todo lo que esté después de este "
             "día se considera un error y se corrige.",
    )

    contract_ids = fields.Many2many(
        "hr.contract", compute="_compute_preview", string="Contratos a corregir",
        help="Contratos abiertos cuya fecha de término hay que ajustar (o definir "
             "por primera vez) a la fecha real.",
    )
    work_entry_count = fields.Integer(
        compute="_compute_preview", string="Asistencias a eliminar",
        help="Registros de asistencia posteriores a la fecha real, sin importar su "
             "estado actual (incluye los ya validados).",
    )
    payslip_ids = fields.Many2many(
        "hr.payslip", "hr_termination_correction_payslip_rel", "wizard_id", "payslip_id",
        compute="_compute_preview", string="Liquidaciones a recalcular",
        help="Liquidaciones cuyo período llega después de la fecha real y que "
             "todavía se pueden corregir (borrador o en verificación).",
    )
    blocked_payslip_ids = fields.Many2many(
        "hr.payslip", "hr_termination_correction_blocked_rel", "wizard_id", "payslip_id",
        compute="_compute_preview", string="Liquidaciones protegidas (revisión manual)",
        help="Validadas, pagadas o históricas: bloquean toda la operación. "
             "Nómina debe revisar la corrección sin modificar su historia.",
    )
    has_action = fields.Boolean(compute="_compute_preview")
    confirm = fields.Boolean(
        string="Confirmo que quiero aplicar esta corrección",
        help="Esta acción recalcula liquidaciones abiertas y elimina asistencia "
             "posterior al término. No tiene deshacer automático.",
    )

    # ------------------------------------------------------------------
    # Vista previa
    # ------------------------------------------------------------------
    def _cutoff_datetime(self):
        self.ensure_one()
        calendar = self.employee_id.resource_calendar_id
        zone = pytz.timezone(calendar.tz or "UTC")
        end = zone.localize(datetime.combine(self.actual_termination_date, time.max))
        return end.astimezone(pytz.UTC).replace(tzinfo=None)

    def _affected_payslips(self):
        """Do not let a hidden or stale payslip turn closed history into zero."""
        self.ensure_one()
        slips = self.env["hr.payslip"].sudo().search([
            ("employee_id", "=", self.employee_id.id),
            ("company_id", "=", self.company_id.id),
            ("date_to", ">", self.actual_termination_date),
        ]).with_env(self.env)
        slips.check_access("read")
        return slips

    def _affected_contracts(self):
        self.ensure_one()
        contracts = self.env["hr.contract"].sudo().search([
            ("employee_id", "=", self.employee_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "!=", "cancel"),
            "|", ("date_start", "=", False), ("date_start", "<=", self.actual_termination_date),
            "|", ("date_end", "=", False), ("date_end", ">", self.actual_termination_date),
        ]).with_env(self.env)
        contracts.check_access("read")
        return contracts

    def _work_entry_domain(self):
        return [("employee_id", "=", self.employee_id.id),
                ("company_id", "=", self.company_id.id),
                ("date_start", ">", self._cutoff_datetime())]

    @api.depends("employee_id", "actual_termination_date")
    def _compute_preview(self):
        for wizard in self:
            if not wizard.employee_id or not wizard.actual_termination_date:
                wizard.contract_ids = False
                wizard.work_entry_count = 0
                wizard.payslip_ids = False
                wizard.blocked_payslip_ids = False
                wizard.has_action = False
                continue

            wizard.employee_id.check_access("read")
            wizard.contract_ids = wizard._affected_contracts()
            wizard.work_entry_count = self.env["hr.work.entry"].search_count(wizard._work_entry_domain())
            affected = wizard._affected_payslips()
            wizard.blocked_payslip_ids = affected.filtered(history_protected)
            wizard.payslip_ids = affected - wizard.blocked_payslip_ids

            wizard.has_action = bool(
                wizard.contract_ids or wizard.work_entry_count or affected)

    @api.onchange("employee_id")
    def _onchange_employee(self):
        if self.employee_id and not self.actual_termination_date:
            last_contract = self.employee_id.contract_ids.filtered(
                lambda c: c.date_end).sorted("date_end", reverse=True)[:1]
            if last_contract:
                self.actual_termination_date = last_contract.date_end

    # ------------------------------------------------------------------
    # Aplicar
    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("steps_hr_payroll_correction.group_payroll_correction"):
            raise AccessError(_("Esta corrección requiere el permiso específico de Nómina."))
        self.check_access("write")
        self.employee_id.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(_("Seleccione una compañía autorizada para este trabajador."))
        if not self.confirm:
            raise UserError(_(
                "Marque la casilla de confirmación antes de aplicar la corrección."))
        # Read again on the server: preview fields and their RPC values cannot
        # authorize a correction, and a slip can have been validated meanwhile.
        slips = self._affected_payslips()
        if slips:
            self.env.cr.execute("SELECT id FROM hr_payslip WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (slips.ids,))
            slips.invalidate_recordset([name for name in ("state", "paid", "step_history_locked") if name in slips._fields])
        blocked = slips.filtered(history_protected)
        if blocked:
            raise UserError(_(
                "Hay liquidaciones validadas, pagadas o históricas en el rango "
                "afectado (%s). La operación completa queda bloqueada; Nómina "
                "debe revisar una corrección que preserve sus importes originales.") % ", ".join(blocked.mapped("name")))
        contracts = self._affected_contracts()
        contracts.check_access("write")
        extra_entries = self.env["hr.work.entry"].sudo().search(self._work_entry_domain())
        # The correction role permits the technical reset of validated entries,
        # but never grants visibility through another company's/record's rules.
        extra_entries.with_env(self.env).check_access("read")
        if self.env["hr.work.entry"].sudo().search_count([
                ("employee_id", "=", self.employee_id.id), ("company_id", "=", self.company_id.id),
                ("date_start", "<=", self._cutoff_datetime()), ("date_stop", ">", self._cutoff_datetime())]):
            raise UserError(_("Hay una entrada de trabajo que cruza el término real; revise sus horas antes de corregir."))
        if not (contracts or extra_entries or slips):
            raise UserError(_(
                "No hay nada que corregir para %(employee)s con esa fecha: ni contratos, "
                "ni asistencia, ni liquidaciones posteriores al %(date)s.",
                employee=self.employee_id.display_name, date=self.actual_termination_date))
        slips.check_access("write")
        for slip in slips:
            # The OCA adapter refreshes actual entries in compute_sheet. A
            # structure still using theoretical OCA days is not admitted here.
            if not hasattr(slip, "_compute_worked_days_line_ids") and not (
                    "use_work_entries" in slip.struct_id._fields and slip.struct_id.use_work_entries):
                raise UserError(_("Active las entradas reales de trabajo antes de corregir esta nómina."))
        with self.env.cr.savepoint():
            return self._apply_open_correction(contracts, extra_entries, slips)

    def _apply_open_correction(self, contracts, extra_entries, slips):
        """One atomic correction, after authorization and whole-batch admission."""

        # 2. Asistencia posterior a la fecha real: a borrador y eliminar.
        # Un registro de asistencia validado no se puede eliminar directamente
        # bajo ninguna circunstancia (regla de Odoo, no de permisos); hay que
        # devolverlo a borrador primero. Eliminar asistencia también está
        # restringido al mismo grupo técnico, por eso el sudo(). Esto va
        # **antes** de tocar el contrato: si se acorta `date_end` con esta
        # asistencia todavía validada, el propio `hr.contract.write()` de
        # Odoo intenta borrarla de golpe y choca con la misma regla.
        removed = len(extra_entries)
        extra_entries.write({"state": "draft"})
        extra_entries.unlink()

        # 3. Contratos: fecha de término real, ya sin asistencia de más en el camino.
        for contract in contracts:
            old_end = contract.date_end
            contract.write({"date_end": self.actual_termination_date})
            contract.message_post(body=_(
                "Corrección de finiquito: fecha de término ajustada de %(old)s a "
                "%(new)s por %(user)s.",
                old=old_end or _("(sin definir)"),
                new=self.actual_termination_date,
                user=self.env.user.display_name))

        # 4. Recalcular cada liquidación afectada desde la asistencia ya corregida.
        # No las volvemos a confirmar: la validación final de un finiquito
        # (vacaciones proporcionales, indemnización, etc.) es una decisión de
        # nómina que debe revisar una persona.
        recomputed = self.env["hr.payslip"]
        for slip in slips:
            if "edited" in slip._fields:
                slip.write({"edited": False})
            # Both engines own the refresh and preserve reusable line IDs.
            if hasattr(slip, "_compute_worked_days_line_ids"):
                slip._compute_worked_days_line_ids()
            slip.compute_sheet()
            recomputed |= slip

        self.employee_id.message_post(body=_(
            "Corrección de finiquito aplicada por %(user)s: término real "
            "%(date)s, %(removed)s asistencias eliminadas, %(slips)s "
            "liquidaciones recalculadas y dejadas pendientes de revisión.",
            user=self.env.user.display_name, date=self.actual_termination_date,
            removed=removed, slips=len(recomputed)))

        return {
            "type": "ir.actions.act_window",
            "name": _("Liquidaciones recalculadas"),
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "domain": [("id", "in", recomputed.ids)],
            "context": {"create": False},
        }
