from types import SimpleNamespace

from lxml import etree
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestContractorWorkers(TransactionCase):
    def test_contractor_crew_only_offers_workers_from_its_own_company_and_contractor(self):
        company = self.env.company
        other_company = self.env['res.company'].create({'name': 'QA Empresa Externa'})
        contractor, other_contractor = self.env['res.partner'].create([
            {'name': 'QA Contratista', 'step_contra': True},
            {'name': 'QA Contratista Distinto', 'step_contra': True},
        ])
        employees = self.env['hr.employee']
        valid, foreign, other, inactive = employees.create([
            {'name': 'QA Local', 'company_id': company.id, 'is_contratista': True,
             'contratista_id': contractor.id},
            {'name': 'QA Ajeno', 'company_id': other_company.id, 'is_contratista': True,
             'contratista_id': contractor.id},
            {'name': 'QA Otro', 'company_id': company.id, 'is_contratista': True,
             'contratista_id': other_contractor.id},
            {'name': 'QA Inactivo', 'company_id': company.id, 'is_contratista': True,
             'contratista_id': contractor.id, 'active': False},
        ])
        crews = self.env['hr.salary.custom']
        crew = crews.create({
            'name': 'QA Cuadrilla', 'company_id': company.id,
            'group_type': 'contratista', 'partner_id': contractor.id,
        })
        form = crews.get_view(view_id=self.env.ref('step_hr.view_hr_salary_custom_form').id, view_type='form')
        root = etree.fromstring(form['arch'])
        xpath = "//field[@name='contract_line']/list/field"
        assert not root.xpath(xpath + "[@name='employee_id_domain']")
        field = root.xpath(xpath + "[@name='employee_id']")[0]
        domain = safe_eval(field.get('domain'), {
            'parent': SimpleNamespace(company_id=company.id, partner_id=contractor.id),
        })
        fixtures = [('id', 'in', (valid | foreign | other | inactive).ids)]
        self.assertEqual(employees.with_context(active_test=False).search(fixtures + domain), valid)
        lines = self.env['hr.salary.contract.line']
        line = lines.create({'salary_id': crew.id, 'employee_id': valid.id})
        self.assertEqual(line.employee_id_domain & (valid | foreign | other | inactive), valid)
        for worker in foreign | other | inactive:
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                lines.create({'salary_id': crew.id, 'employee_id': worker.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            crew.partner_id = other_contractor
