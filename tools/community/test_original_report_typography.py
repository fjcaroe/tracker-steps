"""Pure HTML semantic/selector tests, without importing the Odoo registry."""
import importlib.util
from pathlib import Path
import unittest

from lxml import html


SOURCE = Path(__file__).resolve().parents[2] / 'step_payroll_original_report/header_layout.py'
spec = importlib.util.spec_from_file_location('original_report_typography', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return ('<!DOCTYPE html><html style="height:0"><body class="overflow-hidden">'
            '<div id="minimal_layout_report_headers"><div class="header o_company_8_layout">'
            '<img alt="Logo" src="data:image/png;base64,ORIGINAL" data-original="yes"/>'
            '<div name="company_address" class="col-6" id="corporate" data-oe-id="8">'
            '<ul name="company_address_list"><li><span itemprop="name" style="padding:0">'
            'Compañía original</span><address>Chile</address></li></ul></div></div></div>'
            '<div id="footer" style="color:purple">Unchanged footer</div></body></html>')


class CorporateTypographyCase(unittest.TestCase):
    def test_semantic_attributes_text_and_logo_are_exact(self):
        before = html.fromstring(fixture())
        after = html.fromstring(module.stabilize_corporate_typography(fixture()))
        self.assertEqual(before.text_content(), after.text_content())
        self.assertEqual([n.tag for n in before.iter()], [n.tag for n in after.iter()])
        for left, right in zip(before.iter(), after.iter()):
            self.assertEqual({k:v for k,v in left.attrib.items() if k not in ('class', 'style')},
                             {k:v for k,v in right.attrib.items() if k not in ('class', 'style')})
        self.assertEqual(before.xpath('//img')[0].attrib, after.xpath('//img')[0].attrib)

    def test_only_company_address_typography_changes(self):
        after = html.fromstring(module.stabilize_corporate_typography(fixture()))
        self.assertEqual(after.get('style'), 'height:0')
        self.assertEqual(after.xpath('//body')[0].get('class'), 'overflow-hidden')
        self.assertEqual(after.xpath('//*[@id="footer"]')[0].get('style'), 'color:purple')
        address = after.xpath('//*[@name="company_address"]')[0]
        self.assertIn(module.MARKER, address.get('class').split())
        for node in [address, *address.iterdescendants()]:
            self.assertTrue(node.get('style').endswith(module.TYPOGRAPHY))

    def test_repeated_preparation_is_idempotent(self):
        first = module.stabilize_corporate_typography(fixture())
        self.assertEqual(module.stabilize_corporate_typography(first), first)
        tree = html.fromstring(fixture())
        wrapper = tree.xpath('//*[@id="minimal_layout_report_headers"]')[0]
        import copy
        wrapper.append(copy.deepcopy(wrapper[0]))
        batch = html.tostring(tree, encoding='unicode')
        prepared = html.fromstring(module.stabilize_corporate_typography(batch))
        addresses = prepared.xpath('//*[@name="company_address"]')
        self.assertEqual(len(addresses), 2)
        self.assertEqual(prepared.text_content(), tree.text_content())
        self.assertTrue(all(module.MARKER in node.get('class').split() for node in addresses))

    def test_missing_or_ambiguous_structures_are_rejected(self):
        invalid = [fixture().replace('minimal_layout_report_headers', 'other'),
                   fixture().replace('name="company_address"', 'name="other"'),
                   fixture().replace('name="company_address_list"', 'name="other"'),
                   fixture().replace('</ul>', '</ul><ul name="company_address_list"/>')]
        for value in invalid:
            with self.assertRaises(ValueError):
                module.stabilize_corporate_typography(value)
        tree = html.fromstring(fixture())
        wrapper = tree.xpath('//*[@id="minimal_layout_report_headers"]')[0]
        import copy
        bad = copy.deepcopy(wrapper[0])
        bad.xpath('.//*[@name="company_address_list"]')[0].set('name', 'unsupported')
        wrapper.append(bad)
        with self.assertRaises(ValueError):
            module.stabilize_corporate_typography(html.tostring(tree, encoding='unicode'))


if __name__ == '__main__':
    unittest.main()
