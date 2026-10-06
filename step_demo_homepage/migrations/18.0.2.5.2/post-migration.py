"""Update only the commercial homepage heading, preserving live website edits."""
from lxml import etree
from odoo import api, SUPERUSER_ID

TITLE = "ERP agrícola para gestionar tu campo en Chile"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    views = env['ir.ui.view'].search([('key', '=', 'website.homepage'), ('active', '=', True), ('inherit_id', '=', False)])
    for view in views:
        for language in {code for code, _ in env['res.lang'].get_installed()} | {'en_US'}:
            translated = view.with_context(lang=language)
            tree = etree.fromstring(translated.arch_db.encode())
            headings = tree.xpath('//h1[@id="steps-title"]')
            if not headings:
                continue
            assert len(headings) == 1
            heading = headings[0]
            for child in list(heading):
                heading.remove(child)
            heading.text = "ERP agrícola para gestionar"
            etree.SubElement(heading, 'br').tail = ' '
            etree.SubElement(heading, 'em').text = "tu campo en Chile"
            translated.write({'arch_db': etree.tostring(tree, encoding='unicode')})
