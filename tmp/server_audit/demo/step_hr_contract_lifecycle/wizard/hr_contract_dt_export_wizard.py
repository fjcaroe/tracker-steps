# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError


class HrContractDtExportWizard(models.TransientModel):
    """Selección masiva de contratos para carga a la DT. Agrupa
    automáticamente por Cargo + CAE, como exige el instructivo."""

    _name = "hr.contract.dt.export.wizard"
    _description = "Selección masiva para carga DT de contratos"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    fundo_id = fields.Many2one("step.fundo", string="Fundo / sucursal")
    department_id = fields.Many2one("hr.department", string="Departamento")
    job_id = fields.Many2one("hr.job", string="Cargo")
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
    state = fields.Selection(
        [("draft", "Borrador"), ("open", "Vigente")], default="open"
    )
    matched_contract_ids = fields.Many2many("hr.contract", string="Contratos coincidentes")

    def _domain(self):
        domain = [("company_id", "=", self.company_id.id), ("state", "=", self.state)]
        if self.fundo_id:
            domain.append(("fundo_id", "=", self.fundo_id.id))
        if self.department_id:
            domain.append(("department_id", "=", self.department_id.id))
        if self.job_id:
            domain.append(("job_id", "=", self.job_id.id))
        if self.contract_type_id:
            domain.append(("contract_type_id", "=", self.contract_type_id.id))
        if self.labor_modality:
            domain.append(("labor_modality", "=", self.labor_modality))
        return domain

    def action_search(self):
        self.ensure_one()
        self.matched_contract_ids = self.env["hr.contract"].search(self._domain())
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_batches(self):
        self.ensure_one()
        contracts = self.matched_contract_ids or self.env["hr.contract"].search(self._domain())
        if not contracts:
            raise UserError(_("No hay contratos que coincidan con los filtros."))
        groups = defaultdict(lambda: self.env["hr.contract"])
        for contract in contracts:
            key = (contract.job_id.id, contract.cae_code or "")
            groups[key] |= contract
        Batch = self.env["hr.contract.dt.batch"]
        batches = Batch.browse()
        for (job_id, cae_code), group_contracts in groups.items():
            batch = Batch.create(
                {
                    "company_id": self.company_id.id,
                    "job_id": job_id,
                    "cae_code": cae_code or _("(sin CAE)"),
                    "contract_ids": [(6, 0, group_contracts.ids)],
                }
            )
            batches |= batch
        return {
            "type": "ir.actions.act_window",
            "name": _("Lotes DT generados"),
            "res_model": "hr.contract.dt.batch",
            "view_mode": "list,form",
            "domain": [("id", "in", batches.ids)],
        }
