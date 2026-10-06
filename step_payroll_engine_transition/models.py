from odoo import fields, models, _
from odoo.exceptions import UserError


class LegacySnapshot(models.Model):
    _name = 'step.payroll.legacy.snapshot'
    _description = 'Archivo de nómina anterior'
    _order = 'source_model, source_id'

    source_model = fields.Char(required=True, readonly=True)
    source_id = fields.Integer(required=True, readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    payload = fields.Json(required=True, readonly=True)
    _sql_constraints = [('source_unique', 'unique(source_model,source_id)', 'El registro ya está archivado.')]


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    step_legacy_payroll = fields.Boolean(string='Estructura histórica', readonly=True, copy=False)


class Contract(models.Model):
    _inherit = 'hr.contract'

    step_payroll_migration_review = fields.Boolean(string='Revisar migración de nómina', readonly=True, copy=False)
    step_payroll_migration_mapped = fields.Boolean(readonly=True, copy=False)

    def action_confirm_payroll_migration(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_manager'):
            raise UserError(_('La revisión corresponde al administrador de Nómina.'))
        for contract in self:
            names = ('health_institution', 'pension_option', 'income_tax_type', 'work_schedule_id', 'analytic_account_id', 'contract_type_id')
            if any(not contract[name] for name in names if name in contract._fields):
                raise UserError(_('Complete salud, previsión, jornada, centro de costo y tipo de contrato.'))
            if 'afp_option' not in contract._fields:
                raise UserError(_('Simple Digital no está instalado.'))
            if contract.pension_option == 'afp' and not contract.afp_option:
                raise UserError(_('Seleccione la AFP del contrato.'))
            if not contract.employee_id.hr_commune:
                raise UserError(_('Seleccione la comuna del trabajador.'))
        self.write({'step_payroll_migration_review': False})


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        if any(s.struct_id.step_legacy_payroll for s in self):
            raise UserError(_('Esta liquidación conserva la estructura del motor anterior. No se recalcula; revise la estructura para una nueva liquidación.'))
        if any(s.contract_id.step_payroll_migration_review for s in self):
            raise UserError(_('El contrato requiere revisar sus parámetros de Simple Digital antes de calcular una nueva liquidación.'))
        for slip in self:
            if slip.struct_id.get_external_id().get(slip.struct_id.id) == 'l10n_cl_simpledigital_payroll.structure_chile':
                contract = slip.contract_id
                if any(not contract[name] for name in ('analytic_account_id','health_institution','pension_option','work_schedule_id','income_tax_type','contract_type_id')):
                    raise UserError(_('Complete los parámetros de Simple Digital del contrato antes de calcular.'))
                if not slip.employee_id.hr_commune:
                    raise UserError(_('Seleccione la comuna del trabajador antes de calcular.'))
        return super().compute_sheet()
