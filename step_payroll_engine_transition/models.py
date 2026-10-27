from odoo import fields, models, _
from odoo.exceptions import UserError

_CONFIRM_MIGRATION = object()


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

    def write(self, values):
        if values.get('step_payroll_migration_review') is False and self.env.context.get('_confirm_payroll_migration') is not _CONFIRM_MIGRATION:
            raise UserError(_('Confirme la revisión de parámetros desde el contrato.'))
        return super().write(values)

    def _step_simpledigital_review_issues(self):
        """Explain the existing review checks without confirming or mapping data."""
        self.ensure_one()
        names = ('health_institution', 'pension_option', 'income_tax_type',
                 'work_schedule_id', 'analytic_account_id', 'contract_type_id')
        issues = [self._fields[name].get_description(self.env)['string']
                  for name in names if name in self._fields and not self[name]]
        if 'afp_option' not in self._fields:
            issues.append(_('Simple Digital no está instalado'))
        elif 'pension_option' not in self._fields:
            issues.append(_('Parámetros previsionales de Simple Digital no disponibles'))
        elif self.pension_option == 'afp' and not self.afp_option:
            issues.append(self._fields['afp_option'].get_description(self.env)['string'])
        if 'hr_commune' not in self.employee_id._fields:
            issues.append(_('Comuna del trabajador de Simple Digital no disponible'))
        elif not self.employee_id.hr_commune:
            issues.append(_('Comuna del trabajador'))
        return issues

    def _step_simpledigital_review_lines(self):
        lines = []
        for contract in self.sorted(key=lambda row: row.employee_id.name or row.name or ''):
            issues = contract._step_simpledigital_review_issues()
            detail = (_('Faltan: %s', ', '.join(issues)) if issues
                      else _('Parámetros completos; falta confirmar la revisión'))
            lines.append(_('• %(employee)s — %(contract)s: %(detail)s',
                           employee=contract.employee_id.name or _('Sin trabajador'),
                           contract=contract.name or _('Contrato sin nombre'), detail=detail))
        return '\n'.join(lines)

    def action_confirm_payroll_migration(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_manager'):
            raise UserError(_('La revisión corresponde al administrador de Nómina.'))
        incomplete = self.filtered(lambda contract: contract._step_simpledigital_review_issues())
        if incomplete:
            raise UserError(_('Complete los parámetros antes de confirmar la revisión:\n%s',
                              incomplete._step_simpledigital_review_lines()))
        self.with_context(_confirm_payroll_migration=_CONFIRM_MIGRATION).write({'step_payroll_migration_review': False})


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        if any(s.struct_id.step_legacy_payroll for s in self):
            raise UserError(_('Esta liquidación conserva la estructura del motor anterior. No se recalcula; revise la estructura para una nueva liquidación.'))
        pending = self.mapped('contract_id').filtered('step_payroll_migration_review')
        if pending:
            raise UserError(_(
                'No se pueden calcular nuevas liquidaciones: estos contratos tienen pendiente '
                'la revisión de Simple Digital.\n\n%(contracts)s\n\n'
                'Abra cada contrato y revise sus datos. El administrador de Nómina debe usar '
                '«Confirmar parámetros de nómina» y luego volver a generar los recibos. '
                'Esta confirmación conserva las liquidaciones históricas.',
                contracts=pending._step_simpledigital_review_lines()))
        for slip in self:
            if slip.struct_id.get_external_id().get(slip.struct_id.id) == 'l10n_cl_simpledigital_payroll.structure_chile':
                contract = slip.contract_id
                if any(not contract[name] for name in ('analytic_account_id','health_institution','pension_option','work_schedule_id','income_tax_type','contract_type_id')):
                    raise UserError(_('Complete los parámetros de Simple Digital del contrato antes de calcular.'))
                if not slip.employee_id.hr_commune:
                    raise UserError(_('Seleccione la comuna del trabajador antes de calcular.'))
        return super().compute_sheet()
