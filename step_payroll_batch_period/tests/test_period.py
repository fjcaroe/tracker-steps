"""Real wizard admission on both engines; actual OCA generation, no EE mocks."""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from lxml import etree

from odoo import api, Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import json_default

from ..models import _oca, _PERIOD_SCOPE, _public_result, period_bounds


@tagged('post_install', '-at_install')
class BatchPeriodCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.oca = _oca(cls.env)
        cls.company = cls.env['res.company'].create({'name': 'Private payroll period company',
            'country_id': cls.env.ref('base.cl').id, 'currency_id': cls.env.ref('base.CLP').id})
        group = 'payroll.group_payroll_manager' if cls.oca else 'hr_payroll.group_hr_payroll_manager'
        actor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private payroll period manager', 'login': 'private-payroll-period-manager', 'tz': 'UTC',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(xmlid).id for xmlid in
                ('base.group_user', group, 'hr.group_hr_manager', 'account.group_account_manager')])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.entry_type = cls.scope['hr.work.entry.type'].create({'name': 'Private batch attendance', 'code': 'PRIVATE_BATCH_TIME'})
        cls.calendar = cls.scope['resource.calendar'].create({'name': 'Private batch Santiago', 'tz': 'America/Santiago',
            'company_id': cls.company.id, 'attendance_ids': [Command.clear()] + [Command.create({
                'name': 'Private eight-hour shift', 'dayofweek': str(day), 'hour_from': 8, 'hour_to': 16}) for day in range(5)]})
        if 'work_entry_type_id' in cls.calendar.attendance_ids._fields:
            cls.calendar.attendance_ids.work_entry_type_id = cls.entry_type
        cls.kind = cls.scope['hr.payroll.structure.type'].create({'name': 'Private batch structure type'})
        values = {'name': 'Private batch structure', 'code': 'PRIVATE_BATCH', 'type_id': cls.kind.id}
        for name, value in (('company_id', cls.company.id), ('parent_id', False), ('use_work_entries', True)):
            if name in cls.scope['hr.payroll.structure']._fields:
                values[name] = value
        cls.structure = cls.scope['hr.payroll.structure'].create(values)
        cls.journal = cls.scope['account.journal'].create({'name': 'Private batch salary journal', 'code': 'BPP',
            'type': 'general', 'company_id': cls.company.id})
        # A dedicated transactional fixture sequence never consumes an original
        # business counter. Standard nextval's failure gaps remain documented.
        cls.sequence = cls.env['ir.sequence'].create({'name': 'Private batch salary numbering', 'code': 'salary.slip',
            'company_id': cls.company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE/BATCH/'})
        if cls.oca:
            category = cls.scope['hr.salary.rule.category'].create({'name': 'Private batch category', 'code': 'PRIVATE_BATCH_CAT'})
            cls.rule = cls.scope['hr.salary.rule'].create({'name': 'Private batch engine rule', 'code': 'PRIVATE_BATCH_RESULT',
                'struct_id': cls.structure.id, 'company_id': cls.company.id, 'category_id': category.id,
                'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 100})

    def contract(self, name):
        # Provision masters as the fixture author, including the existing
        # lifecycle's real allocation callback. The wizard and all checks below
        # still use the ordinary payroll actor without any additional group.
        author = self.env['hr.contract'].with_company(self.company).env
        employee = author['hr.employee'].create({'name': name, 'company_id': self.company.id})
        values = {'name': name, 'employee_id': employee.id, 'company_id': self.company.id,
            'state': 'open', 'date_start': '2026-01-01', 'wage': 300000,
            'resource_calendar_id': self.calendar.id, 'structure_type_id': self.kind.id}
        for field_name, value in (('struct_id', self.structure.id), ('journal_id', self.journal.id)):
            if field_name in self.scope['hr.contract']._fields:
                values[field_name] = value
        field = self.scope['hr.contract']._fields.get('contract_type_id')
        if field:
            values['contract_type_id'] = self.scope[field.comodel_name].search([], limit=1).id
        contract = author['hr.contract'].create(values)
        contract.resource_calendar_id = self.calendar
        employee.resource_calendar_id = self.calendar
        employee.resource_id.tz = self.calendar.tz
        return contract.with_env(self.scope)

    def entry(self, contract, start, stop):
        return self.scope['hr.work.entry'].create({'name': 'Private batch entry',
            'employee_id': contract.employee_id.id, 'contract_id': contract.id, 'company_id': self.company.id,
            'date_start': start, 'date_stop': stop, 'work_entry_type_id': self.entry_type.id})

    def wizard(self, contracts, start='2026-10-01', end='2026-10-31'):
        values = {'name': 'Private local period batch', 'company_id': self.company.id, 'date_start': start, 'date_end': end}
        if 'struct_id' in self.scope['hr.payslip.run']._fields:
            values['struct_id'] = self.structure.id
        run = self.scope['hr.payslip.run'].create(values)
        values = {'employee_ids': [Command.set(contracts.employee_id.ids)]}
        if 'structure_id' in self.scope['hr.payslip.employees']._fields:
            values['structure_id'] = self.structure.id
        wizard = self.scope['hr.payslip.employees'].with_context(active_id=run.id, active_model='hr.payslip.run').create(values)
        return wizard, run

    def stored_entries(self, rows):
        rows.flush_recordset()
        self.env.cr.execute('SELECT to_jsonb(t) FROM hr_work_entry t WHERE id=ANY(%s) ORDER BY id', (rows.ids,))
        return self.env.cr.fetchall()

    def test_september_conflicts_do_not_block_october_or_get_changed(self):
        contract = self.contract('Private outside-period worker')
        rows = self.entry(contract, '2026-09-30 11:30:00', '2026-09-30 16:30:00')
        rows |= self.entry(contract, '2026-09-30 11:30:00', '2026-09-30 15:30:00')
        wizard, run = self.wizard(contract)
        before = self.stored_entries(rows)
        data = wizard._step_batch_period_preflight()
        self.assertFalse(data['conflicts'])
        self.assertFalse(data['entries'])
        self.assertEqual(self.stored_entries(rows), before)
        self.assertFalse(run.slip_ids)

    def test_real_october_conflicts_remain_blocked(self):
        contract = self.contract('Private inside-period worker')
        rows = self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
        rows |= self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 15:30:00')
        wizard, run = self.wizard(contract)
        before = self.stored_entries(rows)
        result = wizard.compute_sheet()
        self.assertEqual(result['tag'], 'display_notification')
        json.dumps(result, default=json_default)
        self.assertFalse(run.slip_ids)
        self.assertEqual(self.stored_entries(rows), before)
        internal = {'context': dict(wizard.env.context, _steps_batch_period=(
            _PERIOD_SCOPE, run.id, '2026-10-01', '2026-10-31', ((contract.employee_id.id, contract.id),)))}
        # Official json_default may stringify arbitrary objects. The contract
        # is to remove the capability, never to rely on an encoder exception.
        public_text = json.dumps(_public_result(internal), default=json_default)
        public = json.loads(public_text)
        self.assertNotIn('_steps_batch_period', public['context'])
        self.assertNotIn(str(_PERIOD_SCOPE), public_text)

    def test_local_midnight_and_intersecting_overnight_entries(self):
        contract = self.contract('Private boundary worker')
        outside = self.entry(contract, '2026-10-01 01:00:00', '2026-10-01 03:00:00')
        crossing = self.entry(contract, '2026-10-01 02:00:00', '2026-10-01 04:00:00')
        ending = self.entry(contract, '2026-11-01 03:00:00', '2026-11-01 04:00:00')
        self.assertEqual((outside | crossing | ending)._step_entries_in_batch_period('2026-10-01', '2026-10-31'), crossing)

    def test_external_context_cannot_disable_normal_validation(self):
        contract = self.contract('Private token worker')
        rows = self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
        rows |= self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 15:30:00')
        wizard, run = self.wizard(contract)
        before = self.stored_entries(rows)
        for token in (('fake', '2026-09-01', '2026-09-30'), ['fake'], {'0': 'fake'}, True):
            result = wizard.with_context(_steps_batch_period=token, default_date_start='2026-09-01', contract=False).compute_sheet()
            self.assertEqual(result['tag'], 'display_notification')
            json.dumps(result, default=json_default)
        self.assertFalse(run.slip_ids)
        self.assertEqual(self.stored_entries(rows), before)

    def test_notification_identifies_all_workers_in_local_time(self):
        first = self.contract('Private worker A')
        second = self.contract('Private worker B')
        for contract in first | second:
            self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
            self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 15:30:00')
        wizard, run = self.wizard(first | second)
        result = wizard.compute_sheet()
        for text in ('Private worker A', 'Private worker B', '05/10/2026 08:30', 'America/Santiago'):
            self.assertIn(text, result['params']['message'])
        self.assertTrue(result['params']['sticky'])
        self.assertFalse(run.slip_ids)
        self.assertNotIn('_steps_batch_period', json.dumps(result, default=json_default))
        arch = etree.fromstring(wizard.get_view(view_type='form')['arch'])
        self.assertTrue(arch.xpath("//field[@name='employee_ids']"))
        self.assertTrue(arch.xpath("//button[@name='compute_sheet']"))

    def test_dst_boundaries_use_real_short_and_long_santiago_days(self):
        contract = self.contract('Private daylight-saving worker')
        first, last = period_bounds(contract, '2026-09-06', '2026-09-06')
        self.assertEqual(first, datetime(2026, 9, 6, 4))
        self.assertEqual(last, datetime(2026, 9, 7, 3))
        self.assertEqual(last - first, timedelta(hours=23))
        first, last = period_bounds(contract, '2026-04-04', '2026-04-04')
        self.assertEqual(last - first, timedelta(hours=25))

    def test_hidden_entry_and_contract_block_complete_batch_under_normal_actor(self):
        contract = self.contract('Private hidden-record worker')
        row = self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
        wizard, run = self.wizard(contract)
        before = self.stored_entries(row)
        for xmlid, record in (('hr_work_entry.model_hr_work_entry', row), ('hr_contract.model_hr_contract', contract)):
            restriction = self.env['ir.rule'].create({'name': 'Private hidden batch input', 'model_id': self.env.ref(xmlid).id,
                'domain_force': "[('id','!=',%d)]" % record.id})
            with self.assertRaises(AccessError):
                wizard.sudo().compute_sheet()
            restriction.unlink()
            self.assertFalse(run.slip_ids)
            self.assertEqual(self.stored_entries(row), before)
        for field in (row._fields['date_start'], self.calendar._fields['tz']):
            # Exercise actual field-access checks, never a provider response or
            # an imported Enterprise class. No role is added to the actor.
            with patch.object(field, 'groups', 'base.group_system'), self.assertRaises(AccessError):
                wizard.sudo().compute_sheet()
            self.assertFalse(run.slip_ids)
            self.assertEqual(self.stored_entries(row), before)

    def test_closed_run_wrong_model_missing_run_and_invalid_dates_are_rejected(self):
        contract = self.contract('Private invalid-scope worker')
        wizard, run = self.wizard(contract)
        for context in ({'active_id': False}, {'active_id': 2**30}, {'active_model': 'hr.employee'}):
            with self.assertRaises(UserError):
                wizard.with_context(**context).compute_sheet()
        with self.assertRaises(UserError):
            period_bounds(contract, '2026-11-01', '2026-10-01')
        if 'step_legacy_payroll' in self.structure._fields:
            self.structure.step_legacy_payroll = True
            with self.assertRaisesRegex(UserError, 'histórica'):
                wizard.compute_sheet()
            self.assertTrue(self.structure.step_legacy_payroll)
            self.structure.step_legacy_payroll = False
        if 'step_payroll_migration_review' in contract._fields:
            contract.step_payroll_migration_review = True
            with self.assertRaisesRegex(UserError, 'revisión'):
                wizard.compute_sheet()
            self.assertTrue(contract.step_payroll_migration_review)
        run.state = 'close'
        with self.assertRaises(UserError):
            wizard.compute_sheet()
        self.assertFalse(run.slip_ids)

    def test_wrong_company_context_is_rejected_without_new_payroll(self):
        contract = self.contract('Private company worker')
        wizard, run = self.wizard(contract)
        other = self.env['res.company'].create({'name': 'Private other batch company', 'country_id': self.company.country_id.id})
        self.scope.user.with_env(self.env).write({'company_ids': [Command.link(other.id)]})
        caller = wizard.with_context(allowed_company_ids=(self.company | other).ids).with_company(other)
        with self.assertRaisesRegex(UserError, 'compañía del lote'):
            caller.compute_sheet()
        self.assertFalse(run.slip_ids)

    def test_oca_real_wizard_creates_actual_days_and_preserves_original_entries(self):
        if not self.oca:
            self.skipTest('OCA-specific adapter; native success remains the original provider.')
        contract = self.contract('Private actual OCA batch worker')
        row = self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
        archived = self.entry(contract, '2026-10-06 11:30:00', '2026-10-06 14:30:00')
        archived.active = False
        wizard, run = self.wizard(contract)
        before = self.stored_entries(row | archived)
        result = wizard.with_context(active_test=False).compute_sheet()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        self.assertNotIn('_steps_batch_period', json.dumps(result, default=json_default))
        self.assertEqual(len(run.slip_ids), 1)
        slip = run.slip_ids
        self.assertEqual(slip.contract_id, contract)
        self.assertEqual(slip.state, 'verify')
        self.assertEqual(slip.worked_days_line_ids.work_entry_type_id, self.entry_type)
        self.assertEqual(sum(slip.worked_days_line_ids.mapped('number_of_hours')), row.duration)
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertEqual(self.stored_entries(row | archived), before)
        saved_ids = slip.ids
        with self.assertRaises(UserError):
            wizard.compute_sheet()
        self.assertEqual(run.slip_ids.ids, saved_ids)

    def test_oca_missing_actual_policy_or_entries_never_persist_theoretical_days(self):
        if not self.oca:
            self.skipTest('Community admission does not replace the native generation policy.')
        contract = self.contract('Private no-theoretical worker')
        wizard, run = self.wizard(contract)
        with self.assertRaisesRegex(UserError, 'entradas reales'):
            wizard.compute_sheet()
        self.assertFalse(run.slip_ids)
        self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
        self.rule.split_move_lines = True
        self.scope.flush_all()
        self.env.cr.execute('SELECT last_value,is_called FROM hr_payslip_id_seq')
        before_ids = self.env.cr.fetchone()
        with self.assertRaises(UserError):
            wizard.compute_sheet()
        self.env.cr.execute('SELECT last_value,is_called FROM hr_payslip_id_seq')
        self.assertEqual(self.env.cr.fetchone(), before_ids, 'Known configuration must be rejected before creating even a draft payslip')
        self.assertFalse(run.slip_ids)
        self.assertTrue(self.rule.split_move_lines)
        self.rule.split_move_lines = False
        self.structure.use_work_entries = False
        with self.assertRaisesRegex(UserError, 'política real'):
            wizard.compute_sheet()
        self.assertFalse(run.slip_ids)

    def test_oca_actual_engine_error_rolls_back_created_slips_and_private_number(self):
        if not self.oca:
            self.skipTest('No monetary native formula is inferred by this provider-neutral block.')
        contract = self.contract('Private failing real batch worker')
        row = self.entry(contract, '2026-10-05 11:30:00', '2026-10-05 16:30:00')
        wizard, run = self.wizard(contract)
        self.rule.write({'amount_select': 'code', 'amount_python_compute': 'result = 1 / 0'})
        self.scope.flush_all()
        before = self.stored_entries(row)
        original_number = self.sequence.number_next_actual
        with self.assertRaises(UserError):
            wizard.compute_sheet()
        self.assertFalse(run.slip_ids)
        self.assertEqual(self.stored_entries(row), before)
        self.sequence.invalidate_recordset(['number_next', 'number_next_actual'])
        self.assertEqual(self.sequence.number_next_actual, original_number)
