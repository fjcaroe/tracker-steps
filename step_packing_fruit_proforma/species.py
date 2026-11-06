"""Explicit per-company tax choices, inherited by authorized holding branches."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Species(models.Model):
    _inherit = 'step.especie'

    step_fruit_vat_policy = fields.Selection(
        [('standard', 'Sin cambio de sujeto'), ('withholding', 'Con cambio de sujeto')],
        company_dependent=True, groups='account.group_account_user')
    step_fruit_retention_property_id = fields.Many2one(
        'account.tax', company_dependent=True, groups='account.group_account_user')
    step_change_subject_vat = fields.Boolean(
        'Cambio sujeto IVA', compute='_compute_fruit_vat_policy',
        inverse='_inverse_fruit_subject', groups='account.group_account_user',
        help='Configuración de la empresa activa. Las sucursales heredan la política de su matriz salvo configuración propia.')
    step_withholding_tax_id = fields.Many2one(
        'account.tax', string='Retención', compute='_compute_fruit_vat_policy',
        inverse='_inverse_fruit_retention', groups='account.group_account_user',
        domain="[('type_tax_use','=','purchase'),('amount_type','=','percent'),('amount','<',0),('active','=',True)]",
        help='Seleccione el impuesto de retención ya configurado. El factor se toma de ese impuesto, no del nombre de la especie.')

    def _fruit_vat_policy_for(self, company, validate=False):
        self.ensure_one()
        # Only ancestry metadata is elevated. The selected tax is returned in the
        # caller's environment and retains its native ACL and company checks.
        chain = company.sudo().search([('id', 'parent_of', company.id)]).sorted(
            key=lambda row: len(row.parent_path or ''), reverse=True)
        policy = False
        tax_id = False
        for ancestor in chain:
            config = self.sudo().with_company(ancestor)
            value = config.step_fruit_vat_policy
            if policy is False and value:
                policy = value
            if policy == 'standard':
                break
            if policy == 'withholding':
                tax_id = config.step_fruit_retention_property_id.id
                if tax_id:
                    break
                if value == 'standard':
                    break
        tax = self.env['account.tax'].browse(tax_id)
        subject = policy == 'withholding'
        if subject and tax:
            tax.check_access('read')
            if (not tax.active or tax.type_tax_use != 'purchase' or tax.amount_type != 'percent'
                    or tax.amount >= 0 or tax.price_include
                    or not tax.filtered_domain(tax._check_company_domain(company))):
                raise ValidationError(_('Seleccione una retención porcentual negativa de compras, excluida del precio y compatible con la empresa.'))
        if validate and subject and not tax:
            raise ValidationError(_('Seleccione el impuesto de Retención en la especie %s para esta empresa o su matriz.') % self.display_name)
        return subject, tax if subject else self.env['account.tax']

    @api.depends('step_fruit_vat_policy', 'step_fruit_retention_property_id')
    @api.depends_context('company', 'allowed_company_ids')
    def _compute_fruit_vat_policy(self):
        for species in self:
            subject, tax = species._fruit_vat_policy_for(self.env.company)
            species.step_change_subject_vat = subject
            species.step_withholding_tax_id = tax

    def _inverse_fruit_subject(self):
        for species in self:
            species.step_fruit_vat_policy = 'withholding' if species.step_change_subject_vat else 'standard'

    def _inverse_fruit_retention(self):
        for species in self:
            species.step_fruit_retention_property_id = species.step_withholding_tax_id
