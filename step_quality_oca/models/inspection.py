"""Operate the real AGPL inspection engine without native quality aliases."""
from math import isfinite
from psycopg2 import sql

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.addons.step_quality_contracts.access import FINAL_STATES, children, mutable, normal_read
from odoo.addons.step_quality_contracts.agriculture import inspection_summary, advisor_summary


LINE_FIELDS = ['inspection_id', 'test_line', 'question_type', 'possible_ql_values',
    'qualitative_value', 'quantitative_value', 'min_value', 'max_value', 'uom_id', 'test_uom_id']
VALUE_FIELDS = ['test_line', 'name', 'ok']


def _stored_result(records):
    normal = normal_read(records, ['success'])
    normal.env.cr.execute(sql.SQL('SELECT id,success FROM {} WHERE id=ANY(%s)').format(
        sql.Identifier(normal._table)), (normal.ids,))
    stored = dict(normal.env.cr.fetchall())
    for record in normal:
        if record.id not in stored or stored[record.id] is None:
            raise UserError(_('Adopt the original stored quality result before reading this history.'))
        record.env.cache.set(record, record._fields['success'], bool(stored[record.id]))


def _answers(lines):
    """Read every physical allowed answer, including one hidden by a rule."""
    field = lines._fields['possible_ql_values']
    lines.flush_recordset(['possible_ql_values'])
    lines.env.cr.execute(sql.SQL('SELECT {},{} FROM {} WHERE {}=ANY(%s)').format(
        sql.Identifier(field.column1), sql.Identifier(field.column2), sql.Identifier(field.relation),
        sql.Identifier(field.column1)), (lines.ids,))
    pairs = lines.env.cr.fetchall()
    normal_read(lines.env['qc.test.question.value'].browse(sorted({row[1] for row in pairs})), VALUE_FIELDS)
    return pairs


class Inspection(models.Model):
    _inherit = 'qc.inspection'

    def read(self, fields=None, load='_classic_read'):
        normal = normal_read(self, fields)
        return super(Inspection, normal).read(fields=fields, load=load)

    def copy_data(self, default=None):
        normal = normal_read(self, [name for name, field in self._fields.items() if field.copy and field.store])
        return super(Inspection, normal).copy_data(default=default)

    def copy(self, default=None):
        normal = normal_read(self, [name for name, field in self._fields.items() if field.copy and field.store])
        return super(Inspection, normal).copy(default=default)

    @api.model_create_multi
    def create(self, values_list):
        normal = self.sudo(False)
        normal.check_access('create')
        for values in values_list:
            normal.check_field_access_rights('write', list(values))
            if values.get('state') in FINAL_STATES or 'success' in values:
                raise UserError(_('Create an open real inspection and run its actual quality workflow.'))
            if values.get('test'):
                normal_read(normal.env['qc.test'].browse(values['test']), ['company_id'])
        return super(Inspection, normal).create(values_list)

    def write(self, values):
        normal = self.sudo(False)
        normal.check_access('write')
        normal.check_field_access_rights('write', list(values))
        business = {'name', 'company_id', 'object_id', 'product_id', 'qty', 'test', 'inspection_lines',
            'state', 'date', 'date_done', 'user', 'internal_notes', 'external_notes'}
        if business & values.keys():
            mutable(normal)
        if 'success' in values:
            raise UserError(_('Quality results are computed from the real inspection lines.'))
        if values.get('test'):
            test = normal_read(normal.env['qc.test'].browse(values['test']), ['company_id'])
            if any(test.company_id and test.company_id != record.company_id for record in normal):
                raise UserError(_('The original quality test must belong to the inspection company.'))
        if values.get('state') in ('success', 'failed', 'waiting'):
            normal._step_quality_admission()
            for record in normal:
                allowed = ('ready', 'waiting') if values['state'] == 'success' else ('waiting',) if values['state'] == 'failed' else ('ready',)
                if record.state not in allowed:
                    raise UserError(_('Use the original ready/waiting workflow before closing quality evidence.'))
                if record.state == 'waiting' and not normal.env.user.has_group('quality_control_oca.group_quality_control_manager'):
                    raise UserError(_('A quality manager must approve an inspection.'))
                if values['state'] == 'success' and not record.success or values['state'] in ('failed', 'waiting') and record.success:
                    raise UserError(_('The requested quality state differs from the actual measured result.'))
            if values['state'] == 'failed' and not normal.env.user.has_group('quality_control_oca.group_quality_control_manager'):
                raise UserError(_('A quality manager must approve a failed inspection.'))
        with normal.env.cr.savepoint():
            return super(Inspection, normal).write(values)

    def unlink(self):
        normal = mutable(self)
        normal.check_access('unlink')
        return super(Inspection, normal).unlink()

    @api.depends('inspection_lines', 'inspection_lines.success')
    def _compute_success(self):
        normal = normal_read(self, ['state'])
        frozen = normal.filtered(lambda record: record.state in FINAL_STATES)
        _stored_result(frozen)
        pending = normal - frozen
        if pending:
            return super(Inspection, pending)._compute_success()

    def _step_quality_admission(self, answers_required=True):
        normal = mutable(self)
        normal_read(normal, ['company_id', 'test', 'inspection_lines', 'object_id', 'product_id', 'state', 'qty'])
        for record in normal:
            if type(record.id) is not int or not record.company_id or record.company_id not in normal.env.companies:
                raise UserError(_('Select a saved inspection in its authorized original company.'))
            if not isfinite(record.qty) or record.qty <= 0:
                raise UserError(_('The actual inspected quantity must be positive and finite.'))
            test = normal_read(record.test, ['active', 'company_id', 'test_lines', 'fill_correct_values'])
            if not test or not test.active or test.company_id and test.company_id != record.company_id:
                raise UserError(_('Select an active real quality test in the inspection company.'))
            if test.fill_correct_values:
                raise UserError(_('Use measured answers; this operation does not certify automatically prefilled quality values.'))
            questions = children(test, 'qc.test.question', 'test', ['test', 'type', 'ql_values', 'min_value', 'max_value', 'uom_id'])
            question_answers = children(questions, 'qc.test.question.value', 'test_line', VALUE_FIELDS)
            lines = children(record, 'qc.inspection.line', 'inspection_id', LINE_FIELDS)
            if not questions or len(lines) != len(questions) or set(lines.test_line.ids) != set(questions.ids):
                raise UserError(_('Every original test question needs exactly one real inspection line.'))
            pairs = _answers(lines)
            allowed = {line.id: {value for owner, value in pairs if owner == line.id} for line in lines}
            chosen = normal_read(lines.qualitative_value, VALUE_FIELDS)
            normal_read(lines.uom_id | lines.test_uom_id, ['category_id', 'factor', 'rounding'])
            lines.flush_recordset(['question_type', 'quantitative_value', 'min_value', 'max_value'])
            normal.env.cr.execute('SELECT id,quantitative_value,min_value,max_value FROM qc_inspection_line WHERE id=ANY(%s)', (lines.ids,))
            stored = {row[0]: row[1:] for row in normal.env.cr.fetchall()}
            for line in lines:
                if line.question_type != line.test_line.type:
                    raise UserError(_('The inspection question type differs from its original test.'))
                if line.question_type == 'qualitative':
                    expected = set(question_answers.filtered(lambda value: value.test_line == line.test_line).ids)
                    if not expected or allowed[line.id] != expected:
                        raise UserError(_('The inspection must retain all original allowed answers of its question.'))
                    if line.qualitative_value:
                        if line.qualitative_value.id not in allowed[line.id] or line.qualitative_value.test_line != line.test_line:
                            raise UserError(_('Select an allowed answer of this exact original quality question.'))
                    elif answers_required:
                        raise UserError(_('Provide a real answer to every qualitative question.'))
                elif line.question_type == 'quantitative':
                    if not line.uom_id or not line.test_uom_id or line.uom_id.category_id != line.test_uom_id.category_id:
                        raise UserError(_('Quality measurements require compatible original units of measure.'))
                    measurement, lower, upper = stored[line.id]
                    # The real set-test wizard creates an unmeasured draft.
                    # Preparing it must retain SQL NULL, not manufacture zero;
                    # only confirming/approving requires an actual measurement.
                    if (any(value is None or not isfinite(value) for value in (lower, upper))
                            or measurement is not None and not isfinite(measurement)
                            or answers_required and measurement is None):
                        raise UserError(_('Quality measurements and limits must be stored and finite; NULL is not zero.'))
                    if line.min_value > line.max_value:
                        raise UserError(_('The original quality limits are reversed.'))
                    if (line.test_uom_id != line.test_line.uom_id or line.min_value != line.test_line.min_value
                            or line.max_value != line.test_line.max_value):
                        raise UserError(_('Refresh the real inspection from its original test before using changed limits.'))
                else:
                    raise UserError(_('Select an actual supported quality question type.'))
            if record.object_id:
                record.object_id.check_access('read')
                if 'company_id' in record.object_id._fields and record.object_id.company_id and record.object_id.company_id != record.company_id:
                    raise UserError(_('Quality evidence must refer to the original inspection company.'))
        return normal

    def action_todo(self):
        normal = self._step_quality_admission(answers_required=False)
        with normal.env.cr.savepoint():
            return super(Inspection, normal).action_todo()

    def action_confirm(self):
        normal = self._step_quality_admission()
        if any(record.state != 'ready' for record in normal):
            raise UserError(_('Only ready inspections can be confirmed.'))
        with normal.env.cr.savepoint():
            return super(Inspection, normal).action_confirm()

    def action_approve(self):
        normal = self._step_quality_admission()
        if not normal.env.user.has_group('quality_control_oca.group_quality_control_manager'):
            raise UserError(_('A quality manager must approve an inspection.'))
        if any(record.state != 'waiting' for record in normal):
            raise UserError(_('Only inspections waiting for approval can be approved.'))
        with normal.env.cr.savepoint():
            return super(Inspection, normal).action_approve()

    @api.model
    def get_step_quality_overview(self):
        normal = self.sudo(False)
        normal_read(normal, ['state'])
        return {'provider': 'quality_control_oca', 'native_identity_converted': False,
            'scope': 'visible_records_only', 'total': normal.search_count([]),
            'passed': normal.search_count([('state', '=', 'success')]),
            'failed': normal.search_count([('state', '=', 'failed')]),
            'pending': normal.search_count([('state', 'in', ['plan', 'draft', 'ready', 'waiting'])]),
            'inspections': inspection_summary(normal.env, []), 'advisors': advisor_summary(normal.env, [])}


class InspectionLine(models.Model):
    _inherit = 'qc.inspection.line'

    def read(self, fields=None, load='_classic_read'):
        normal = normal_read(self, fields)
        return super(InspectionLine, normal).read(fields=fields, load=load)

    def copy_data(self, default=None):
        normal = normal_read(self, [name for name, field in self._fields.items() if field.copy and field.store])
        return super(InspectionLine, normal).copy_data(default=default)

    @api.model_create_multi
    def create(self, values_list):
        normal = self.sudo(False)
        normal.check_access('create')
        for values in values_list:
            self._step_finite_values(values)
            normal.check_field_access_rights('write', list(values))
            if not values.get('inspection_id') or 'success' in values:
                raise UserError(_('Create a real inspection line on its open original inspection.'))
            mutable(normal.env['qc.inspection'].browse(values['inspection_id']))
            if values.get('test_line'):
                normal_read(normal.env['qc.test.question'].browse(values['test_line']), ['test'])
            if values.get('qualitative_value'):
                normal_read(normal.env['qc.test.question.value'].browse(values['qualitative_value']), VALUE_FIELDS)
        return super(InspectionLine, normal).create(values_list)

    def write(self, values):
        self._step_finite_values(values)
        normal = normal_read(self, ['inspection_id'])
        normal.check_access('write')
        normal.check_field_access_rights('write', list(values))
        mutable(normal.inspection_id)
        if values.get('inspection_id'):
            mutable(normal.env['qc.inspection'].browse(values['inspection_id']))
        if 'success' in values:
            raise UserError(_('Quality line results are computed from the real measurements.'))
        if values.get('qualitative_value'):
            normal_read(normal.env['qc.test.question.value'].browse(values['qualitative_value']), VALUE_FIELDS)
        return super(InspectionLine, normal).write(values)

    def _step_finite_values(self, values):
        for name in ('quantitative_value', 'min_value', 'max_value'):
            if name in values and (values[name] is None or not isfinite(values[name])):
                raise UserError(_('Quality measurements and limits must be finite.'))

    def unlink(self):
        normal = normal_read(self, ['inspection_id'])
        normal.check_access('unlink')
        mutable(normal.inspection_id)
        return super(InspectionLine, normal).unlink()

    @api.depends('question_type', 'uom_id', 'test_uom_id', 'max_value', 'min_value',
        'quantitative_value', 'qualitative_value', 'qualitative_value.ok', 'possible_ql_values')
    def _compute_quality_test_check(self):
        normal = normal_read(self, LINE_FIELDS)
        normal_read(normal.inspection_id, ['state'])
        frozen = normal.filtered(lambda record: record.inspection_id.state in FINAL_STATES)
        _stored_result(frozen)
        pending = normal - frozen
        converted = pending.filtered(lambda record: record.question_type == 'quantitative'
            and record.uom_id and record.test_uom_id and record.uom_id != record.test_uom_id)
        normal_read(converted.uom_id | converted.test_uom_id, ['category_id', 'factor', 'rounding'])
        normal_read(pending.qualitative_value, VALUE_FIELDS)
        for line in converted:
            if line.uom_id.category_id != line.test_uom_id.category_id:
                line.success = False
            else:
                # Use the real official UoM API, preserving source quantities.
                amount = line.uom_id._compute_quantity(line.quantitative_value, line.test_uom_id, round=False)
                line.success = line.max_value >= amount >= line.min_value
        other = pending - converted
        if other:
            return super(InspectionLine, other)._compute_quality_test_check()


class QuestionValue(models.Model):
    _inherit = 'qc.test.question.value'

    def _step_protect_used_answers(self):
        normal = normal_read(self, VALUE_FIELDS)
        field = normal.env['qc.inspection.line']._fields['possible_ql_values']
        normal.env['qc.inspection.line'].flush_model(['inspection_id', 'qualitative_value', 'possible_ql_values'])
        normal.env['qc.inspection'].flush_model(['state'])
        normal.env.cr.execute(sql.SQL('SELECT 1 FROM qc_inspection_line l JOIN qc_inspection i ON i.id=l.inspection_id '
            'WHERE i.state=ANY(%s) AND (l.qualitative_value=ANY(%s) OR EXISTS(SELECT 1 FROM {} r '
            'WHERE r.{}=l.id AND r.{}=ANY(%s))) LIMIT 1').format(sql.Identifier(field.relation),
                sql.Identifier(field.column1), sql.Identifier(field.column2)), (list(FINAL_STATES), normal.ids, normal.ids))
        if normal.env.cr.fetchone():
            raise UserError(_('An answer used by finalized quality evidence retains its original identity and meaning.'))
        return normal

    def write(self, values):
        normal = self.sudo(False)
        normal.check_access('write')
        normal.check_field_access_rights('write', list(values))
        if {'name', 'ok', 'test_line'} & values.keys():
            normal = normal._step_protect_used_answers()
        return super(QuestionValue, normal).write(values)

    def unlink(self):
        normal = self.sudo(False)
        normal.check_access('unlink')
        normal = normal._step_protect_used_answers()
        return super(QuestionValue, normal).unlink()


class SetTest(models.TransientModel):
    _inherit = 'qc.inspection.set.test'

    def action_create_test(self):
        normal = normal_read(self, ['test'])
        normal.ensure_one()
        context = normal.env.context
        if context.get('active_model') != 'qc.inspection' or type(context.get('active_id')) is not int:
            raise UserError(_('Select the actual saved OCA inspection before setting its test.'))
        inspection = mutable(normal.env['qc.inspection'].browse(context['active_id']))
        inspection.check_access('write')
        with normal.env.cr.savepoint():
            result = super(SetTest, normal).action_create_test()
            inspection._step_quality_admission(answers_required=False)
            return result
