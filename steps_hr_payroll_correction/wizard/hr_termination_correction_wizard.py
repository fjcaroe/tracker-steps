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
- Desbloquea (si hace falta) y recalcula las liquidaciones afectadas.

Las liquidaciones ya **pagadas** nunca se tocan automáticamente: el dinero ya
salió, así que quedan marcadas para revisión manual en vez de corregirse solas.
"""

from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
             "todavía se pueden corregir (borrador, en verificación o confirmadas).",
    )
    blocked_payslip_ids = fields.Many2many(
        "hr.payslip", "hr_termination_correction_blocked_rel", "wizard_id", "payslip_id",
        compute="_compute_preview", string="Liquidaciones pagadas (requieren revisión manual)",
        help="Ya se pagaron: no se tocan automáticamente. Corríjalas a mano si "
             "corresponde, evaluando el impacto en lo ya pagado.",
    )
    has_action = fields.Boolean(compute="_compute_preview")
    confirm = fields.Boolean(
        string="Confirmo que quiero aplicar esta corrección",
        help="Esta acción desbloquea liquidaciones ya confirmadas y elimina "
             "asistencia validada. No tiene deshacer automático.",
    )

    # ------------------------------------------------------------------
    # Vista previa
    # ------------------------------------------------------------------
    def _cutoff_datetime(self):
        self.ensure_one()
        return datetime.combine(self.actual_termination_date, time(23, 59, 59))

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

            cutoff = wizard.actual_termination_date
            wizard.contract_ids = wizard.employee_id.contract_ids.filtered(
                lambda c: c.state != "cancel"
                and (not c.date_start or c.date_start <= cutoff)
                and (not c.date_end or c.date_end > cutoff))

            wizard.work_entry_count = self.env["hr.work.entry"].search_count([
                ("employee_id", "=", wizard.employee_id.id),
                ("date_start", ">", wizard._cutoff_datetime()),
            ])

            affected_domain = [
                ("employee_id", "=", wizard.employee_id.id),
                ("date_to", ">", cutoff),
            ]
            wizard.payslip_ids = self.env["hr.payslip"].search(
                affected_domain + [("state", "in", ("draft", "verify", "done"))])
            wizard.blocked_payslip_ids = self.env["hr.payslip"].search(
                affected_domain + [("state", "=", "paid")])

            wizard.has_action = bool(
                wizard.contract_ids or wizard.work_entry_count or wizard.payslip_ids)

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
        if not self.confirm:
            raise UserError(_(
                "Marque la casilla de confirmación antes de aplicar la corrección."))
        if not self.has_action:
            raise UserError(_(
                "No hay nada que corregir para %(employee)s con esa fecha: ni contratos, "
                "ni asistencia, ni liquidaciones posteriores al %(date)s.",
                employee=self.employee_id.display_name, date=self.actual_termination_date))
        if self.blocked_payslip_ids:
            raise UserError(_(
                "Hay liquidaciones ya pagadas dentro del rango afectado (%s). Esas no se "
                "corrigen automáticamente: requieren revisión manual porque el pago ya "
                "se realizó.") % ", ".join(self.blocked_payslip_ids.mapped("name")))

        cutoff_dt = self._cutoff_datetime()

        # 1. Liquidaciones confirmadas: desbloquear antes de tocar nada más.
        # `action_payslip_cancel` exige el grupo técnico de Administrador de
        # sistema para cancelar una liquidación 'done'. El resguardo real de
        # esta herramienta es su propio permiso (group_payroll_correction) más
        # la casilla de confirmación y el registro de auditoría de más abajo,
        # así que se opera con sudo() para no exigirle a quien la usa el
        # perfil completo de Administrador de sistema.
        done_slips = self.payslip_ids.filtered(lambda p: p.state == "done")
        if done_slips:
            done_slips.sudo().action_payslip_cancel()
            done_slips.sudo().action_payslip_draft()

        # 2. Asistencia posterior a la fecha real: a borrador y eliminar.
        # Un registro de asistencia validado no se puede eliminar directamente
        # bajo ninguna circunstancia (regla de Odoo, no de permisos); hay que
        # devolverlo a borrador primero. Eliminar asistencia también está
        # restringido al mismo grupo técnico, por eso el sudo(). Esto va
        # **antes** de tocar el contrato: si se acorta `date_end` con esta
        # asistencia todavía validada, el propio `hr.contract.write()` de
        # Odoo intenta borrarla de golpe y choca con la misma regla.
        extra_entries = self.env["hr.work.entry"].sudo().search([
            ("employee_id", "=", self.employee_id.id),
            ("date_start", ">", cutoff_dt),
        ])
        removed = len(extra_entries)
        extra_entries.write({"state": "draft"})
        extra_entries.unlink()

        # 3. Contratos: fecha de término real, ya sin asistencia de más en el camino.
        for contract in self.contract_ids:
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
        for slip in self.payslip_ids:
            slip = slip.exists()
            if not slip or slip.state not in ("draft", "verify"):
                continue
            slip.write({"edited": False})
            slip.worked_days_line_ids.unlink()
            slip.line_ids.unlink()
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
