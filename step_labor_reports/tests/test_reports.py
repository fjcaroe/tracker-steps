import base64,io,zipfile
from odoo.tests import TransactionCase, tagged, Form
from odoo.tests.common import new_test_user
from odoo.addons.step_labor_reports.hooks import pre_init_hook,post_init_hook
from odoo.addons.step_labor_reports.ownership import RECORDS

@tagged('post_install','-at_install')
class LaborReportsCase(TransactionCase):
    def test_original_identifiers_and_idempotent_ownership(self):
        for key in RECORDS:
            self.assertEqual(self.env.ref('step_hr.'+key),self.env.ref('step_labor_reports.'+key))
        rows=self.env['ir.model.relation'].search([('name','in',('employee_wizard_rel','employee_process_rel'))])
        original=rows.read(['name','model','module'])
        pre_init_hook(self.env);post_init_hook(self.env)
        self.assertEqual(rows.read(['name','model','module']),original)
        self.assertEqual(rows.module.name,'step_labor_reports')

    def test_native_report_downloads_with_original_employee_relation(self):
        user=new_test_user(self.env,login='private_labor_reports',groups='base.group_user,hr.group_hr_user')
        employee=self.env['hr.employee'].create({'name':'Private labor report worker'})
        self.env['step.tarja'].create({'name':'Private report source','date':'2099-01-01',
            'tarja_line':[(0,0,{'employee_id':employee.id,'quantity':2})],
            'tarja_cost_line':[(0,0,{'employee_id':employee.id,'quantity':3,'tarifa':20})]})
        for model,view in [('report.step.hrs.wizard','report_step_hrs_wizard_form'),
                           ('report.by.process.wizard','report_step_by_process_form')]:
            scoped=self.env[model].with_user(user)
            with Form(scoped,view='step_labor_reports.'+view) as form:
                form.date_from='2099-01-01';form.date_to='2099-01-02'
                form.employee_ids.add(employee)
            wizard=form.record
            self.assertEqual(wizard.employee_ids,employee)
            action=wizard.generate_report()
            self.assertEqual(action['res_id'],wizard.id)
            raw=base64.b64decode(wizard.file)
            with zipfile.ZipFile(io.BytesIO(raw)) as book:
                self.assertIn('xl/worksheets/sheet1.xml',book.namelist())
                self.assertIn(b'Private labor report worker',book.read('xl/sharedStrings.xml'))
                if model=='report.by.process.wizard':
                    from xml.etree import ElementTree as ET
                    sheet=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
                    values=sheet.findall(".//{*}c[@r='AB2']/{*}v")
                    self.assertTrue(values)
                    self.assertEqual(float(values[0].text),60)

    def test_portal_cannot_read_operational_reports(self):
        portal=new_test_user(self.env,login='private_labor_reports_portal',groups='base.group_portal')
        for model in ('report.step.hrs.wizard','report.by.process.wizard'):
            self.assertFalse(self.env[model].with_user(portal).has_access('read'))
