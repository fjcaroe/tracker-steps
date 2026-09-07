"""Reglas previsionales que complementan el motor SimpleDigital."""

from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _step_previred_active_over_65(self):
        """Indica si corresponde al tipo de trabajador 3 de PreviRed.

        El generador del proveedor determina la edad al primer día del período
        declarado. Se replica exactamente ese corte para que el cálculo de la
        liquidación y el campo 12 del TXT nunca discrepen.
        """
        self.ensure_one()
        contract = self.contract_id
        birthday = self.employee_id.birthday
        period_date = self.date_from
        if not birthday or not period_date or contract.is_retired_elderly:
            return False
        age = period_date.year - birthday.year - (
            (period_date.month, period_date.day)
            < (birthday.month, birthday.day)
        )
        return age > 65
