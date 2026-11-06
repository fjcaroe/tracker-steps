"""Export explicitly classified, stored retroactive family allowances."""
from decimal import Decimal, ROUND_HALF_UP
from odoo import _, fields, models
from odoo.addons.step_hr_previred.tools import previred


class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    step_previred_family_retroactive = fields.Boolean(
        string='Asignación familiar retroactiva (Previred 23)',
        help='Informa en el campo 23 el total guardado de esta regla en la '
             'liquidación. Requiere empleador adherido a CCAF. No recalcula '
             'la regla ni modifica los haberes del recibo.')


class PreviredExtractor(models.AbstractModel):
    _inherit = 'step.previred.extractor'

    def _enrich_official_fields(self, record, payslip, dataset):
        result = super()._enrich_official_fields(record, payslip, dataset)
        if len(record.principal) != previred.FIELD_COUNT:
            return result
        # Configuration is metadata; salaries remain the already authorized
        # payslip lines selected by the canonical company/period extractor.
        lines = payslip.line_ids.filtered(
            lambda line: line.salary_rule_id.sudo().step_previred_family_retroactive)
        if not lines:
            return result
        # Closed/imported line totals are the evidence. Do not recompute a paid
        # line from its current amount, quantity, rate or a renamed rule code.
        self.env.cr.execute('SELECT COALESCE(SUM(total), 0) FROM hr_payslip_line '
                            'WHERE id = ANY(%s) AND slip_id = %s',
                            (lines.ids, payslip.id))
        total = Decimal(str(self.env.cr.fetchone()[0]))
        ccaf = str(record.principal[82] or '').strip()
        if not total.is_finite() or total < 0:
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_ERROR, 'family_retroactive_invalid',
                _('La asignación familiar retroactiva debe tener un total '
                  'guardado no negativo; revise la liquidación.'),
                record.department_label))
            return result
        if total and ccaf in ('', '0', '00'):
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_ERROR, 'family_retroactive_without_ccaf',
                _('El campo 23 de asignación familiar retroactiva requiere '
                  'una CCAF configurada para el empleador.'),
                record.department_label))
            return result
        record.principal[22] = str(int(total.quantize(
            Decimal('1'), rounding=ROUND_HALF_UP)))
        return result
