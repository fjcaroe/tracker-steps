"""Ordinary actor fixtures for native payroll storage, without computation."""
from odoo import Command
from odoo.exceptions import AccessError, UserError
from psycopg2 import sql

from .testing import PayrollContractMixin


class HistoryStorageCases:
    """Explicit wrappers belong to the real provider's TransactionCase."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        class FixtureRoot:
            @classmethod
            def setUpClass(cls):
                pass

        class Fixture(PayrollContractMixin, FixtureRoot):
            payroll_group = cls.payroll_group
            oca = cls.oca

        Fixture.env = cls.env
        Fixture.setUpClass()
        cls.case = Fixture()
        cls.env['res.lang']._activate_lang('es_CL')

    def _raw(self, record):
        record.flush_recordset()
        self.env.cr.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t WHERE id=%s').format(
            sql.Identifier(record._table)), (record.id,))
        return self.env.cr.fetchone()[0]

    def _line(self):
        case = self.case
        slip = case.slip(amount=0)
        line = case.scope['hr.payslip.line'].create({
            'name': 'Private stored name: acción  doble', 'code': 'PRIVATE_HISTORY_STORAGE',
            'slip_id': slip.id, 'salary_rule_id': case.rule.id, 'employee_id': case.employee.id,
            'contract_id': case.contract.id, 'category_id': case.rule.category_id.id,
            'amount': 1, 'quantity': 1, 'rate': 100})
        self.assertFalse(line.env.su)
        return slip, line

    def case_line_literal_does_not_inherit_master_translation_or_change_on_read(self):
        if self.oca:
            from odoo.addons.step_payroll_oca_api.models.original_history_storage import _admit_literal_line_storage
            # Isolated PostgreSQL fixtures exercise the pre-init refusal;
            # no payroll table, historical literal or master is rewritten.
            self.env.cr.execute('CREATE TEMP TABLE private_history_literal_jsonb (name jsonb) ON COMMIT DROP')
            self.env.cr.execute('CREATE TEMP TABLE private_history_literal_varchar (name varchar) ON COMMIT DROP')
            with self.assertRaises(UserError):
                _admit_literal_line_storage(self.env.cr, 'private_history_literal_jsonb')
            self.env.cr.execute('INSERT INTO private_history_literal_varchar VALUES (NULL)')
            with self.assertRaises(UserError):
                _admit_literal_line_storage(self.env.cr, 'private_history_literal_varchar')
            self.env.cr.execute('SELECT name FROM private_history_literal_varchar')
            self.assertEqual(self.env.cr.fetchall(), [(None,)])
            self.env.cr.execute('DELETE FROM private_history_literal_varchar')
            self.env.cr.execute('INSERT INTO private_history_literal_varchar VALUES (%s)', ('Private literal á  doble',))
            _admit_literal_line_storage(self.env.cr, 'private_history_literal_varchar')
            self.env.cr.execute('SELECT name FROM private_history_literal_varchar')
            self.assertEqual(self.env.cr.fetchall(), [('Private literal á  doble',)])
        slip, line = self._line()
        field = line._fields['name']
        self.assertFalse(field.translate)
        self.assertEqual(field.column_type, ('varchar', 'VARCHAR'))
        before = self._raw(line)
        self.assertEqual(before['name'], 'Private stored name: acción  doble')
        for language in ('en_US', 'es_CL'):
            self.assertEqual(line.with_context(lang=language).read(['name']), [{'id': line.id, 'name': before['name']}])
        self.case.rule.with_context(lang='es_CL').write({'name': 'Private changed rule name'})
        line.invalidate_recordset(['name'])
        self.assertEqual(line.name, before['name'])
        self.assertEqual(self._raw(line), before)
        self.assertEqual(slip.state, 'draft')
        self.assertFalse(slip.paid)

    def case_rule_translation_uses_jsonb_without_translating_existing_line(self):
        slip, line = self._line()
        rule = self.case.rule.with_context(lang='en_US')
        self.assertTrue(rule._fields['name'].translate)
        self.assertEqual(rule._fields['name'].column_type, ('jsonb', 'jsonb'))
        original = rule.name
        before_line = self._raw(line)
        rule.with_context(lang='es_CL').write({'name': 'Private regla traducida áé'})
        raw = self._raw(rule)
        self.assertEqual(raw['name']['en_US'], original)
        self.assertEqual(raw['name']['es_CL'], 'Private regla traducida áé')
        before_rule = self._raw(rule)
        self.assertEqual(rule.with_context(lang='en_US').name, original)
        self.assertEqual(rule.with_context(lang='es_CL').name, 'Private regla traducida áé')
        self.assertEqual(self._raw(rule), before_rule)
        self.assertEqual(self._raw(line), before_line)
        self.assertEqual(slip.state, 'draft')

    def case_worked_day_null_is_created_and_read_without_backfill(self):
        case = self.case
        slip = case.slip(amount=0)
        kind = case.scope['hr.work.entry.type'].create({'name': 'Private nullable history work',
            'code': 'PRIVATE_HISTORY_STORAGE_WORK'})
        day = case.scope['hr.payslip.worked_days'].create({'name': False, 'payslip_id': slip.id,
            'contract_id': case.contract.id, 'work_entry_type_id': kind.id, 'code': kind.code,
            'number_of_days': 0, 'number_of_hours': 0})
        self.assertFalse(day.env.su)
        self.assertFalse(day._fields['name'].required)
        before = self._raw(day)
        self.assertIsNone(before['name'])
        self.assertEqual(day.read(['name']), [{'id': day.id, 'name': False}])
        kind.name = 'Private changed work label'
        day.invalidate_recordset(['name'])
        self.assertFalse(day.name)
        self.assertEqual(self._raw(day), before)
        self.assertEqual(slip.state, 'draft')

    def case_contract_calendar_is_nullable_and_actual_fk_sets_null(self):
        case = self.case
        calendar = case.scope['resource.calendar'].create({'name': 'Private removable history calendar',
            'company_id': case.company.id, 'attendance_ids': [Command.clear()]})
        contract = case.contract.with_env(self.env).copy({'name': 'Private nullable calendar contract',
            'state': 'draft', 'resource_calendar_id': calendar.id}).with_env(case.scope)
        self.assertFalse(contract.env.su)
        field = contract._fields['resource_calendar_id']
        self.assertFalse(field.required)
        self.assertEqual(field.ondelete, 'set null')
        self.env.cr.execute("""SELECT k.confdeltype,k.convalidated FROM pg_constraint k
            JOIN pg_attribute a ON a.attrelid=k.conrelid AND k.conkey=ARRAY[a.attnum]::smallint[]
            JOIN pg_attribute b ON b.attrelid=k.confrelid AND k.confkey=ARRAY[b.attnum]::smallint[]
            WHERE k.contype='f' AND k.conrelid='hr_contract'::regclass
            AND k.confrelid='resource_calendar'::regclass AND a.attname='resource_calendar_id' AND b.attname='id'""")
        self.assertEqual(self.env.cr.fetchall(), [('n', True)])
        calendar.check_access('unlink')
        calendar.unlink()
        contract.invalidate_recordset(['resource_calendar_id'])
        self.assertFalse(contract.resource_calendar_id)
        self.assertIsNone(self._raw(contract)['resource_calendar_id'])
        contract.write({'resource_calendar_id': False})
        before = self._raw(contract)
        self.assertEqual(contract.read(['resource_calendar_id']), [{'id': contract.id, 'resource_calendar_id': False}])
        self.assertEqual(self._raw(contract), before)
        self.assertEqual(contract.state, 'draft')

    def case_history_storage_still_rejects_portal_actor_with_warm_cache(self):
        slip, line = self._line()
        line.read(['name'])
        before = self._raw(line)
        portal = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private storage portal', 'login': 'private-history-storage-portal',
            'groups_id': [Command.set(self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(AccessError):
            line.with_user(portal).sudo(False).read(['name'])
        self.assertEqual(self._raw(line), before)
        self.assertEqual(slip.state, 'draft')
