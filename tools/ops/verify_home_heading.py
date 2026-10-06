"""Effective QWeb and module-source check in an Odoo shell."""
import importlib
from lxml import etree

try:
    module = env['ir.module.module'].search([('name', '=', 'step_demo_homepage')])
    assert module.latest_version == EXPECTED['step_demo_homepage']
    assert importlib.import_module('odoo.addons.step_demo_homepage').__file__.startswith(ROOT + '/')
    page = env['ir.ui.view'].search([('key', '=', 'website.homepage'), ('website_id', '=', 1), ('active', '=', True)], limit=1)
    assert page
    for language in {code for code, _ in env['res.lang'].get_installed()} | {'en_US'}:
        tree = etree.fromstring(page.with_context(lang=language).arch_db.encode())
        headings = tree.xpath('//h1[@id="steps-title"]')
        assert len(headings) == 1
        assert ' '.join(''.join(headings[0].itertext()).split()) == 'ERP agrícola para gestionar tu campo en Chile'
        assert len(tree.xpath('//article[@class="steps-product"]')) == 20
    print('MANAGEMENT_REGISTRY_OK homepage ' + module.latest_version)
finally:
    env.cr.rollback()
