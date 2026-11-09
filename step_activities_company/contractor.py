from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ContractorCrew(models.Model):
    _inherit = 'hr.salary.custom'

    @api.constrains('company_id', 'partner_id', 'group_type')
    def _check_contractor_crew_workers(self):
        self.contract_line._check_contractor_worker()


class ContractorCrewLine(models.Model):
    _inherit = 'hr.salary.contract.line'

    employee_id_domain = fields.Many2many(store=False, compute_sudo=False)

    def _contractor_worker_domain(self):
        self.ensure_one()
        crew = self.salary_id
        if crew.group_type != 'contratista' or not crew.company_id or not crew.partner_id:
            return [('id', '=', False)]
        return [
            ('active', '=', True),
            ('is_contratista', '=', True),
            ('company_id', '=', crew.company_id.id),
            ('contratista_id', '=', crew.partner_id.id),
        ]

    @api.depends('salary_id.group_type', 'salary_id.company_id', 'salary_id.partner_id')
    @api.depends_context('uid', 'company')
    def _compute_employee_id(self):
        employees = self.env['hr.employee']
        for line in self:
            line.employee_id_domain = employees.search(line._contractor_worker_domain())

    @api.constrains('employee_id', 'salary_id')
    def _check_contractor_worker(self):
        employees = self.env['hr.employee']
        for line in self:
            if line.salary_id.group_type != 'contratista' or not line.employee_id:
                continue
            domain = [*line._contractor_worker_domain(), ('id', '=', line.employee_id.id)]
            if not employees.search_count(domain, limit=1):
                raise ValidationError(_(
                    'Seleccione un trabajador activo del contratista y de la empresa de la cuadrilla.'
                ))
