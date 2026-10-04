from odoo import _, fields, models, api
from odoo.exceptions import ValidationError


class StepTrackerCostCenter(models.Model):
    _inherit = 'step.tracker.cost_center'

    management_center_id = fields.Many2one(
        'step.management.cost.center', string='Centro de Gestión y Costos', check_company=True,
        help='Selección explícita cuando varias fichas de Gestión y Costos usan la misma cuenta analítica.')

    @api.constrains('management_center_id', 'analytic_account_id')
    def _check_management_center(self):
        for center in self:
            managed = center.management_center_id
            if managed and managed.analytic_account_id and center.analytic_account_id \
                    and managed.analytic_account_id != center.analytic_account_id:
                raise ValidationError(_(
                    'El centro de Gestión y Costos %(center)s usa otra cuenta analítica que el centro de Tracker.'
                ) % {'center': managed.display_name})


class StepManagementCostCenter(models.Model):
    _inherit = 'step.management.cost.center'

    def action_open_tracker_costs(self):
        self.ensure_one()
        return self.env['step.tracker.cost.wizard'].action_open(scope='center', center=self)
