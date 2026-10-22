from lxml import etree
from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


class FolioSettingsCase(TransactionCase):
    def test_menu_selects_existing_companies_and_native_form(self):
        action = self.env.ref('step_export_shipping_design.folio_company_action')
        menu = self.env.ref('step_export_shipping_design.folio_company_menu')
        self.assertEqual(menu.action, action)
        self.assertEqual(action.res_model, 'res.company')
        context = safe_eval(action.context)
        self.assertFalse(context['create'])
        self.assertFalse(context['delete'])
        self.assertEqual([mode for _, mode in action.views], ['list', 'form'])
        listing = etree.fromstring(self.env['res.company'].get_view(
            view_id=action.views[0][0], view_type='list')['arch'])
        self.assertEqual(listing.get('create'), 'false')
        self.assertEqual(listing.get('delete'), 'false')
        domain = safe_eval(action.domain, {'allowed_company_ids': self.env.companies.ids})
        self.assertEqual(domain, [('id', 'in', self.env.companies.ids)])
        view = 'step_export_shipping_design.folio_company_form'
        form = etree.fromstring(self.env['res.company'].get_view(view_id=self.env.ref(view).id, view_type='form')['arch'])
        self.assertEqual(form.xpath("//field[@name='name']")[0].get('readonly'), '1')
        company = self.env.company
        original_name = company.name
        count = self.env['res.company'].search_count([])
        with Form(company, view=view) as editor:
            editor.export_folio_mode = 'shared'
            editor.export_folio_initial = 250
        self.assertEqual(company.name, original_name)
        self.assertEqual(company.export_folio_initial, 250)
        self.assertEqual(company.export_folio_mode, 'shared')
        self.assertEqual(self.env['res.company'].search_count([]), count)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            company.export_folio_initial = 0
