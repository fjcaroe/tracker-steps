from odoo import _, fields, models, api
from odoo.exceptions import ValidationError


class StepTrackerCostCenter(models.Model):
    _inherit = 'step.tracker.cost_center'

    management_center_id = fields.Many2one(
        'account.analytic.account', string='Centro de costo', check_company=True,
        help='Cuenta analítica del centro de costo, compartida con Gestión y Costos.')

    @api.constrains('management_center_id', 'analytic_account_id')
    def _check_management_center(self):
        for center in self:
            managed = center.management_center_id
            if managed and center.analytic_account_id and managed != center.analytic_account_id:
                raise ValidationError(_(
                    'El centro de Gestión y Costos %(center)s usa otra cuenta analítica que el centro de Tracker.'
                ) % {'center': managed.display_name})


class StepManagementCostCenter(models.Model):
    _inherit = 'account.analytic.account'

    def action_open_tracker_costs(self):
        self.ensure_one()
        return self.env['step.tracker.cost.wizard'].action_open(scope='center', center=self)
