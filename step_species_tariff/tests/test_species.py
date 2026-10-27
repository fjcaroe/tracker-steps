from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class SpeciesTariffCase(TransactionCase):
    def test_text_roundtrip_keeps_leading_zeroes_and_punctuation(self):
        original = self.env['step.especie'].search([], limit=1)
        row = self.env['step.especie'].create({'name': 'QA T126', 'type_especie': original.type_especie,
            'group_especie': original.group_especie.id,
            'company_ids': [(6, 0, original.company_ids.ids)], 'tariff_code': '0012.34/A'})
        self.env.invalidate_all()
        self.assertEqual(row.tariff_code, '0012.34/A')
        row.tariff_code = False
        self.assertFalse(row.tariff_code)

    def test_native_form_updates_existing_master_without_replacing_it(self):
        row = self.env['step.especie'].search([], limit=1)
        self.assertTrue(row)
        before = row.read(['id', 'name', 'cod_especie', 'company_ids'])[0]
        with Form(row, view='step_hr.view_step_especie_form') as form:
            form.tariff_code = '000123'
        self.assertEqual(row.tariff_code, '000123')
        self.assertEqual(row.read(['id', 'name', 'cod_especie', 'company_ids'])[0], before)
