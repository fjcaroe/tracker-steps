# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class HrSeveranceSelectionWizard(models.TransientModel):
    """Selección masiva de trabajadores a finiquitar. Detecta contratos
    duplicados, datos faltantes y procesos de finiquito ya abiertos antes
    de crear registros."""

    _name = "hr.severance.selection.wizard"
    _description = "Selección masiva de finiquitos"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    work_location_id = fields.Many2one("hr.work.location", string="Ubicación / sucursal")
    department_id = fields.Many2one("hr.department", string="Departamento")
    contract_type_id = fields.Many2one("hr.contract.type", string="Tipo de contrato")
    labor_modality = fields.Selection(
        [
            ("temporada", "Temporada / faena transitoria"),
            ("trato", "A trato"),
            ("plazo_fijo", "Plazo fijo"),
            ("permanente", "Agrícola permanente / indefinido"),
        ],
        string="Modalidad",
    )
    causal_id = fields.Many2one("step.hr.termination.cause", required=True)
    date_termino = fields.Date(required=True, default=fields.Date.context_today)
    income_type = fields.Selection(
        [("fija", "Renta fija"), ("variable", "Renta variable"), ("mixta", "Renta mixta")],
        default="fija",
        required=True,
    )
    matched_contract_ids = fields.Many2many("hr.contract", string="Contratos coincidentes")

    def _domain(self):
        domain = [("company_id", "=", self.company_id.id), ("state", "=", "open")]
        if self.work_location_id:
            domain.append(("work_location_id", "=", self.work_location_id.id))
        if self.department_id:
            domain.append(("department_id", "=", self.department_id.id))
        if self.contract_type_id:
            domain.append(("contract_type_id", "=", self.contract_type_id.id))
        if self.labor_modality:
            domain.append(("labor_modality", "=", self.labor_modality))
        return domain

    def action_search(self):
        self.ensure_one()
        contracts = self.env["hr.contract"].search(self._domain())
        already_open = self.env["hr.severance"].search(
            [
                ("contract_id", "in", contracts.ids),
                ("state", "not in", ("cancelled", "rejected", "closed")),
            ]
        ).contract_id
        self.matched_contract_ids = contracts - already_open
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_severances(self):
        self.ensure_one()
        contracts = self.matched_contract_ids or self.env["hr.contract"].search(self._domain())
        if not contracts:
            raise UserError(_("No hay contratos que coincidan con los filtros."))
        duplicated = self.env["hr.severance"].search(
            [
                ("contract_id", "in", contracts.ids),
                ("state", "not in", ("cancelled", "rejected", "closed")),
            ]
        )
        if duplicated:
            raise UserError(
                _("Ya existe un proceso de finiquito abierto para: %s")
                % ", ".join(duplicated.mapped("employee_id.name"))
            )
        missing_data = contracts.filtered(lambda c: not c.date_start)
        if missing_data:
            raise UserError(
                _("Contratos sin fecha de inicio, no se puede calcular: %s")
                % ", ".join(missing_data.mapped("employee_id.name"))
            )
        Severance = self.env["hr.severance"]
        severances = Severance.browse()
        for contract in contracts:
            severances |= Severance.create(
                {
                    "company_id": self.company_id.id,
                    "contract_id": contract.id,
                    "causal_id": self.causal_id.id,
                    "date_termino": self.date_termino,
                    "income_type": self.income_type,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Finiquitos creados"),
            "res_model": "hr.severance",
            "view_mode": "list,form",
            "domain": [("id", "in", severances.ids)],
        }
