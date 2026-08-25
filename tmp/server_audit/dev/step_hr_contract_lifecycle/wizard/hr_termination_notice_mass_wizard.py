# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class HrTerminationNoticeMassWizard(models.TransientModel):
    """Selección masiva de trabajadores para emitir carta de aviso.
    Detecta contratos duplicados/ya con un aviso abierto antes de crear
    registros nuevos."""

    _name = "hr.termination.notice.mass.wizard"
    _description = "Selección masiva de avisos de término"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    fundo_id = fields.Many2one("step.fundo", string="Fundo / sucursal")
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
    causal_id = fields.Many2one("hr.causal.termino", required=True)
    date_termino = fields.Date(required=True, default=fields.Date.context_today)
    matched_contract_ids = fields.Many2many("hr.contract", string="Contratos coincidentes")

    def _domain(self):
        domain = [("company_id", "=", self.company_id.id), ("state", "=", "open")]
        if self.fundo_id:
            domain.append(("fundo_id", "=", self.fundo_id.id))
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
        already_open = self.env["hr.termination.notice"].search(
            [("contract_id", "in", contracts.ids), ("state", "!=", "cancelled")]
        ).contract_id
        self.matched_contract_ids = contracts - already_open
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_notices(self):
        self.ensure_one()
        contracts = self.matched_contract_ids or self.env["hr.contract"].search(self._domain())
        if not contracts:
            raise UserError(_("No hay contratos que coincidan con los filtros."))
        duplicated = self.env["hr.termination.notice"].search(
            [("contract_id", "in", contracts.ids), ("state", "!=", "cancelled")]
        )
        if duplicated:
            raise UserError(
                _(
                    "Ya existe un aviso abierto para: %s"
                )
                % ", ".join(duplicated.mapped("employee_id.name"))
            )
        Notice = self.env["hr.termination.notice"]
        notices = Notice.browse()
        for contract in contracts:
            notices |= Notice.create(
                {
                    "company_id": self.company_id.id,
                    "contract_id": contract.id,
                    "causal_id": self.causal_id.id,
                    "date_termino": self.date_termino,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Avisos de término creados"),
            "res_model": "hr.termination.notice",
            "view_mode": "list,form",
            "domain": [("id", "in", notices.ids)],
        }
