# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    treasury_batch_approval_threshold = fields.Monetary(
        related="company_id.treasury_batch_approval_threshold", readonly=False,
    )
    treasury_batch_approver_id = fields.Many2one(
        related="company_id.treasury_batch_approver_id", readonly=False,
    )
