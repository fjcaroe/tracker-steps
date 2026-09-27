"""Corte V2 E — grupo presupuestario controlado "Hora Maquinaria".

`step.management.budget.group` no tenía, hasta este puente, ningún
concepto de grupo "reservado" — es un catálogo libre por empresa. Este
corte introduce exactamente un código reservado (``MACHINERY_GROUP_CODE``)
para que el presupuesto general pueda distinguir sin ambigüedad las líneas
de maquinaria (categoría ``machinery``) que consumen la tarifa calculada
por este puente. El helper es idempotente y no depende de IDs de base de
datos, mismo criterio que ``type.service.machinery._ensure_canonical_catalog``
del addon real de maquinaria (auditado, no modificado).
"""

from odoo import api, fields, models

#: Código reservado del grupo presupuestario de horas de maquinaria. Es una
#: convención propia de este puente (no un dato del cliente ni del addon de
#: maquinaria), así que fijarlo aquí no viola "no hardcodees IDs/nombres
#: reales" — nada de esto proviene de `step_machinery`.
MACHINERY_GROUP_CODE = "HRMAQ"
MACHINERY_GROUP_NAME = "Hora Maquinaria"


class StepManagementBudgetGroup(models.Model):
    _inherit = "step.management.budget.group"

    @api.model
    def get_machinery_group(self, company=None):
        """Devuelve el grupo controlado de horas de maquinaria de `company`,
        creándolo si falta. Idempotente: no duplica si ya existe."""
        company = company or self.env.company
        group = self.sudo().search([
            ("code", "=", MACHINERY_GROUP_CODE), ("company_id", "=", company.id),
        ], limit=1)
        if group:
            return group
        return self.sudo().create({
            "code": MACHINERY_GROUP_CODE, "name": MACHINERY_GROUP_NAME,
            "company_id": company.id, "flow_type": "cost",
        })
