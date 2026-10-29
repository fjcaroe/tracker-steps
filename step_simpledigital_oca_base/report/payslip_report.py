"""Print authorized stored payslip lines through the real OCA/AGPL template.

No payroll rule, current wage, computed header total or overtime computation is
used. SQL preserves SQL NULLs after normal record and field access checks; it
never grants access to another payslip or exposes formulas/configuration.
"""
from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


HABER_CATEGORIES = frozenset(('BASICO', 'IMP', 'SUBSIDIOS', 'GROSS', 'NOP_IMP', 'BRUTO', 'habIMP'))
DEDUCTION_CATEGORIES = frozenset(('AFP', 'SALUD', 'EXD', 'AFC_T', 'IPS', 'APVI', 'APVC_T',
    'CUENTA2', 'RETENCION', 'CCAF_CREDITO', 'CCAF_AHORRO', 'CCAF_DENTAL', 'CCAF_SEG_VIDA', 'CCAF_OTROS', 'others'))


def translated(value, language):
    if not isinstance(value, dict):
        return value
    if value.get(language) is not None:
        return value[language]
    if value.get('en_US') is not None:
        return value['en_US']
    return next((item for item in value.values() if item is not None), None)


def nullable_sum(values):
    """Missing/NULL is not a calculated zero; actual zero and negatives survive."""
    values = list(values)
    return sum(values) if values and all(value is not None for value in values) else None


class StoredPayslipReport(models.AbstractModel):
    _name = 'report.step_simpledigital_oca_base.report_payslip'
    _description = 'Liquidación Community desde líneas almacenadas autorizadas'

    @api.model
    def _get_report_values(self, docids, data=None):
        # Report actions may be resolved with sudo internally. Preserve the
        # authenticated environment UID/context, explicitly drop elevation and
        # never take a UID, company authority or financial payload from data.
        return self.sudo(False)._get_stored_report_values(docids)

    @api.model
    def _get_stored_report_values(self, docids):
        if not isinstance(docids, (list, tuple)) or not docids or any(type(value) is not int or value <= 0 for value in docids):
            raise UserError(_('Select existing payslips to print.'))
        if len(set(docids)) != len(docids):
            raise UserError(_('Select each payslip only once.'))
        docs = self.env['hr.payslip'].with_context(active_test=False).browse(docids)
        docs.check_access('read')
        docs.check_field_access_rights('read', ['name', 'number', 'employee_id', 'company_id', 'struct_id', 'date_from', 'date_to'])
        if set(docs.exists().ids) != set(docids):
            raise UserError(_('A selected payslip no longer exists.'))
        if any(slip.company_id not in self.env.companies for slip in docs):
            raise AccessError(_('The payslip company is not active for this user.'))

        # The complete inverse relation must be admitted before reading values.
        # An ORM One2many alone can silently omit a row hidden by a record rule.
        children = {}
        for model, table, inverse, fields in (
                ('hr.payslip.line', 'hr_payslip_line', 'slip_id',
                 ['name', 'code', 'salary_rule_id', 'category_id', 'appears_on_payslip', 'amount', 'quantity', 'rate', 'total']),
                ('hr.payslip.worked_days', 'hr_payslip_worked_days', 'payslip_id',
                 ['name', 'code', 'number_of_days', 'number_of_hours'])):
            records = self.env[model].with_context(active_test=False)
            records.flush_model([inverse])
            self.env.cr.execute('SELECT id FROM ' + table + ' WHERE ' + inverse + '=ANY(%s) ORDER BY id', [list(docids)])
            records = records.browse([row[0] for row in self.env.cr.fetchall()])
            records.check_access('read')
            records.check_field_access_rights('read', fields)
            children[model] = records

        # Presentation payload does not grant configuration model ACLs, but
        # explicit field groups still apply even to these related labels.
        required = ('payslip_name', 'hide_basic_on_pdf')
        if any(name not in self.env['hr.payroll.structure']._fields for name in required):
            raise UserError(_('Install the original payroll presentation field contract before printing.'))
        self.env['hr.payroll.structure'].check_field_access_rights('read', list(required))
        self.env['hr.salary.rule.category'].check_field_access_rights('read', ['code'])

        self.env.cr.execute("""SELECT l.id,l.slip_id,l.salary_rule_id,l.code,l.appears_on_payslip,
            l.amount,l.quantity,l.rate,l.total,c.code
            FROM hr_payslip_line l LEFT JOIN hr_salary_rule_category c ON c.id=l.category_id
            WHERE l.id=ANY(%s) ORDER BY l.slip_id,l.sequence,l.id""", [children['hr.payslip.line'].ids])
        lines = {row[0]: dict(zip(('id', 'slip_id', 'salary_rule_id', 'code', 'visible',
            'amount', 'quantity', 'rate', 'total', 'category'), row)) for row in self.env.cr.fetchall()}
        self.env.cr.execute('SELECT id,payslip_id,code,number_of_days,number_of_hours '
                            'FROM hr_payslip_worked_days WHERE id=ANY(%s) ORDER BY id',
                            [children['hr.payslip.worked_days'].ids])
        days = {row[0]: dict(zip(('id', 'slip_id', 'code', 'days', 'hours'), row)) for row in self.env.cr.fetchall()}

        # These presentation-only properties belong to the structure of an
        # already authorized slip. Employees do not gain payroll configuration
        # ACLs, arbitrary metadata, formulas or access to another structure.
        structures = set(docs.mapped('struct_id').ids)
        self.env.cr.execute('SELECT id,payslip_name,hide_basic_on_pdf FROM hr_payroll_structure WHERE id=ANY(%s)',
                            [sorted(structures)])
        presentation = {row[0]: {'title': translated(row[1], self.env.lang), 'hide_basic': row[2]} for row in self.env.cr.fetchall()}
        payload = {}
        for slip in docs:
            own = [row for row in lines.values() if row['slip_id'] == slip.id]
            net = [row for row in own if row['code'] == 'NET']
            if any(row['salary_rule_id'] is None for row in net):
                raise UserError(_('A stored NET line has no original salary rule identity.'))
            if len({row['salary_rule_id'] for row in net}) > 1:
                raise UserError(_('Stored NET lines have different rule identities; no amount was selected.'))
            info = presentation.get(slip.struct_id.id, {})
            printable = [row['id'] for row in own if row['visible']
                         and not (info.get('hide_basic') and row['code'] == 'BASIC')]
            own_days = [row for row in days.values() if row['slip_id'] == slip.id and row['code'] != 'OUT']
            payload[slip.id] = {'line_ids': printable, 'visible_ids': [row['id'] for row in own if row['visible']],
                'title': info.get('title') if info.get('title') is not None else slip.name,
                'net': nullable_sum(row['total'] for row in net), 'days': own_days}

        def document(slip):
            if slip._name != 'hr.payslip' or len(slip) != 1 or slip.id not in payload:
                raise AccessError(_('The report cannot read an unrelated payslip.'))
            return payload[slip.id]

        def line_value(line, key='total'):
            if line._name != 'hr.payslip.line' or len(line) != 1 or line.id not in lines:
                raise AccessError(_('The report cannot read an unrelated salary line.'))
            return lines[line.id][key]

        def printed_lines(slip):
            return children['hr.payslip.line'].browse(document(slip)['line_ids'])

        def category_total(slip, codes):
            # Hiding BASIC is presentation only; it does not alter a stored
            # category subtotal or the NET source lines.
            visible = children['hr.payslip.line'].browse(document(slip)['visible_ids'])
            return nullable_sum(line_value(line) for line in visible
                                if line_value(line, 'category') in codes)

        def other_lines(slip):
            return printed_lines(slip).filtered(lambda line: line_value(line, 'category') not in
                HABER_CATEGORIES | DEDUCTION_CATEGORIES | {'TOTAL_DESC'} and line_value(line, 'code') != 'NET')

        return {'doc_ids': list(docids), 'doc_model': 'hr.payslip', 'docs': docs,
            'step_report_lines': printed_lines, 'step_report_total': line_value,
            'step_report_category': lambda line: line_value(line, 'category'),
            'step_report_category_total': category_total, 'step_report_other_lines': other_lines,
            'step_report_title': lambda slip: document(slip)['title'],
            'step_report_net': lambda slip: document(slip)['net'],
            'step_report_days': lambda slip: children['hr.payslip.worked_days'].browse([row['id'] for row in document(slip)['days']]),
            'step_report_day_value': lambda day, key: days[day.id][key],
            'step_report_day_sum': lambda slip, key: nullable_sum(row[key] for row in document(slip)['days']),
            # No overtime amount/hour snapshot has been certified. A current
            # computed overtime value must never be substituted into a history.
            'step_report_overtime_hours': lambda slip: None}
