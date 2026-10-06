"""Update only the commercial homepage heading, preserving live website edits."""
from lxml import etree
from odoo import api, SUPERUSER_ID
import json
from psycopg2.extras import Json

TITLE = "ERP agrícola para gestionar tu campo en Chile"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    key = 'step_demo_homepage.heading_preserved_views'
    preserved = env['ir.config_parameter'].sudo().get_param(key)
    assert preserved, 'Published homepage variants were not preserved'
    for item in json.loads(preserved):
        cr.execute("""UPDATE ir_ui_view SET arch_db=%s,name=%s,website_meta_title=%s,
                      website_meta_description=%s,website_meta_og_img=%s WHERE id=%s""",
                   (Json(item['arch_db']), Json(item['name']), Json(item['website_meta_title']),
                    Json(item['website_meta_description']), item['website_meta_og_img'], item['id']))
    env.invalidate_all()
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
    env['ir.config_parameter'].sudo().search([('key', '=', key)]).unlink()
