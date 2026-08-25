# -*- coding: utf-8 -*-
from odoo import models


class HrContract(models.Model):
    """Mapea el motor SimpleDigital (l10n_cl_simpledigital_payroll) hacia
    la interfaz de adaptación que define el núcleo. No agrega campos
    nuevos: SimpleDigital ya trae afp_option, health_institution,
    work_schedule_id en hr.contract y causal_contract_end_id en
    hr.employee. Ningún cálculo legal ni el motor de liquidaciones de
    SimpleDigital se tocan aquí."""

    _inherit = "hr.contract"

    def _selection_label(self, field_name, value):
        if not value:
            return ""
        selection = dict(self._fields[field_name].selection)
        return selection.get(value, value)

    # -- Interfaz de adaptación (sobreescribe al núcleo) -------------------------
    def _steps_contract_payload(self):
        self.ensure_one()
        payload = super()._steps_contract_payload()
        commune = self.employee_id.hr_commune
        payload.update(
            {
                "work_commune_code": commune.codigo or "",
                "signature_commune_code": commune.codigo or payload.get("signature_commune_code", ""),
                "tipo_jornada_code": self.work_schedule_id or "",
            }
        )
        return payload

    # Códigos de health_institution que representan "no está en isapre"
    # (Fonasa / sin isapre declarada), según el catálogo real de
    # l10n_cl_simpledigital_payroll. El resto de códigos son isapres
    # privadas.
    _FONASA_HEALTH_CODES = ("07 - 102", "00 - 99")

    def _steps_pension_payload(self):
        self.ensure_one()
        is_fonasa = self.health_institution in self._FONASA_HEALTH_CODES
        health_type = "fonasa" if (not self.health_institution or is_fonasa) else "isapre"
        return {
            "afp_name": self._selection_label("afp_option", self.afp_option),
            "health_name": self._selection_label("health_institution", self.health_institution),
            "health_type": health_type,
        }

    def _steps_termination_payload(self):
        self.ensure_one()
        Cause = self.env["step.hr.termination.cause"]
        legacy_causal = self.employee_id.causal_contract_end_id
        if not legacy_causal:
            return super()._steps_termination_payload()
        mapped = Cause.search(
            [
                ("origin_model", "=", "hr.causal.contract.end"),
                ("origin_id", "=", legacy_causal.id),
            ],
            limit=1,
        )
        return {"termination_cause_id": mapped}
