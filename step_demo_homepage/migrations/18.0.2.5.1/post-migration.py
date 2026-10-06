"""Publish the current Spanish home, including website copies and old translations."""
from pathlib import Path

from lxml import etree
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = Path(__file__).resolve().parents[2]
    languages = {code for code, _ in env['res.lang'].get_installed()} | {'en_US'}
    for filename in ('homepage.xml', 'solution_pages.xml'):
        document = etree.parse(str(module / 'views' / filename))
        for record in document.xpath('//record[@model="ir.ui.view"]'):
            local_id = record.get('id')
            if local_id == 'google_site_verification_view':
                continue
            xml_id = local_id if '.' in local_id else 'step_demo_homepage.' + local_id
            original = env.ref(xml_id)
            arch = etree.tostring(record.find('field[@name="arch"]')[0], encoding='unicode')
            values = {'arch_db': arch}
            for field in record.findall('field'):
                if field.get('name') in {'name', 'website_meta_title',
                                        'website_meta_description', 'website_meta_og_img'}:
                    values[field.get('name')] = field.text
            views = original | env['ir.ui.view'].search([
                ('key', '=', original.key), ('inherit_id', '=', False),
                ('active', '=', True),
            ])
            # Builder copies and es_CL translations can otherwise keep the old home.
            for view in views:
                # ir.ui.view.write keeps arch_prev and requires one view per write.
                view.with_context(lang='en_US').write(values)
                for language in sorted(languages - {'en_US'}):
                    view.with_context(lang=language).write(values)
                for language in languages:
                    actual = view.with_context(lang=language).arch_db
                    assert etree.tostring(etree.fromstring(actual.encode()), method='c14n') == \
                        etree.tostring(etree.fromstring(arch.encode()), method='c14n'), \
                        'Homepage translation was not synchronized: %s/%s' % (view.key, language)
