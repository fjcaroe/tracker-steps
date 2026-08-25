# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrLegalCalendarSimulator(models.TransientModel):
    _name = "hr.legal.calendar.simulator"
    _description = "Simulador de adecuación de jornada legal"

    calendar_id = fields.Many2one(
        "hr.legal.workweek.calendar", required=True, string="Transición legal"
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
    affected_contract_ids = fields.Many2many(
        "hr.contract", compute="_compute_affected", string="Contratos afectados"
    )
    affected_count = fields.Integer(compute="_compute_affected")
    total_hours_to_reduce = fields.Float(compute="_compute_affected")

    @api.depends("calendar_id", "company_id")
    def _compute_affected(self):
        for wiz in self:
            contracts = self.env["hr.contract"].browse()
            total_reduce = 0.0
            if wiz.calendar_id and wiz.company_id:
                candidates = self.env["hr.contract"].search(
                    [("company_id", "=", wiz.company_id.id), ("state", "=", "open")]
                )
                for c in candidates:
                    hours = (
                        c.resource_calendar_id.hours_per_week
                        if c.resource_calendar_id
                        else 0.0
                    )
                    if hours > wiz.calendar_id.max_weekly_hours:
                        contracts |= c
                        total_reduce += hours - wiz.calendar_id.max_weekly_hours
            wiz.affected_contract_ids = contracts
            wiz.affected_count = len(contracts)
            wiz.total_hours_to_reduce = total_reduce

    def action_create_batch(self):
        self.ensure_one()
        batch = self.env["hr.contract.adequacy.batch"].create(
            {"calendar_id": self.calendar_id.id, "company_id": self.company_id.id}
        )
        batch.action_simulate()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.contract.adequacy.batch",
            "res_id": batch.id,
            "view_mode": "form",
            "target": "current",
        }
