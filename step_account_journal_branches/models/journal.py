from odoo import api, fields, models


class Journal(models.Model):
    _inherit = 'account.journal'

    step_available_branch_ids = fields.Many2many(
        'res.company', compute='_compute_available_branches',
        string='Sucursales con disponibilidad',
        help='Sucursales activas de la compañía del diario que tiene autorizadas su usuario. '
             'Odoo permite usar automáticamente los diarios de la matriz en sus sucursales. '
             'La compañía propietaria del diario y de cada asiento se conserva.',
    )
    step_branch_scope_ids = fields.Json(compute='_compute_available_branches')

    @api.depends('company_id')
    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_available_branches(self):
        # Read the native hierarchy and existing user memberships. This field
        # neither grants company access nor changes journal accounting domains.
        scope = self.env.user.company_ids.ids
        companies = self.env['res.company'].with_context(allowed_company_ids=scope)
        for journal in self:
            journal.step_branch_scope_ids = scope
            journal.step_available_branch_ids = companies.search([
                ('id', 'child_of', journal.company_id.id),
                ('id', '!=', journal.company_id.id),
                ('id', 'in', self.env.user.company_ids.ids),
            ]) if journal.company_id else companies
