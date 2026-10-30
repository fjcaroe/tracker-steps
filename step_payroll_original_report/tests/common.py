"""Materialize the existing real CE test fixture only after registry admission."""
from odoo import Command
from odoo.tools import SQL


def prepare_ce_fixture(test):
    if test.env['ir.actions.report']._step_original_report_ce_renderer() is None:
        test.skipTest('Stored Community renderer is not installed in the native reference')
    # Deliberately inside the CE-only branch: importing this addon at module
    # import time would register its payroll classes in the native reference.
    from odoo.addons.step_simpledigital_oca_base.tests.report_fixture import StoredReportFixture

    class FixtureBase:
        def setUp(self):
            pass

    class RealStoredFixture(StoredReportFixture, FixtureBase):
        pass

    fixture = RealStoredFixture()
    fixture.env, fixture.skipTest = test.env, test.skipTest
    fixture.setUp()
    report = test.env['ir.actions.report'].create({
        'name': 'Private existing original-language payroll action',
        'model': 'hr.payslip', 'report_type': 'qweb-pdf',
        'report_name': 'hr_payroll.report_payslip_lang',
        'report_file': 'hr_payroll.report_payslip_lang',
        'binding_model_id': test.env['ir.model']._get_id('hr.payslip'),
        'groups_id': [Command.clear()], 'attachment_use': False,
    })
    fixture.structure.report_id = report
    return fixture, report


def action_snapshot(action):
    action.flush_recordset()
    action.env.cr.execute(SQL('SELECT to_jsonb(t) FROM %s t WHERE id=%s', SQL.identifier(action._table), action.id))
    return {'row': action.env.cr.fetchone()[0], 'fields': action.read([
        'id', 'name', 'model', 'report_type', 'report_name', 'report_file',
        'binding_model_id', 'groups_id', 'attachment', 'attachment_use', 'paperformat_id'])}
