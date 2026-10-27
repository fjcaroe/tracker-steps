# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SuccessMessage(models.TransientModel):
    _name = 'success.message'
    _description = "Show Message"

    message = fields.Text('Success', required=True)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
