from odoo.tests import TransactionCase, tagged


@tagged('post_install','-at_install')
class CompanyPreviredCase(TransactionCase):
    def test_native_previred_page_reuses_canonical_fields(self):
        arch=self.env['res.company']._get_view(view_type='form')[0]
        pages=arch.xpath("//page[@name='steps_previred']")
        self.assertEqual(len(pages),1)
        names={node.get('name') for node in pages[0].xpath('.//field')}
        self.assertEqual(names,{'caja_compensacion','has_mutual','mutual','rate_base','rate_additional'})
        self.assertFalse(any(name.startswith('x_') for name in names))
