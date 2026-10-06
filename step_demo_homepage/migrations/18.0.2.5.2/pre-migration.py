"""Preserve published variants before the website XML data is reloaded."""
import json

KEY = 'step_demo_homepage.heading_preserved_views'


def migrate(cr, version):
    cr.execute("""SELECT id,arch_db,name,website_meta_title,website_meta_description,website_meta_og_img
                  FROM ir_ui_view WHERE active AND inherit_id IS NULL
                  AND (key='website.homepage' OR key LIKE 'step_demo_homepage.%%')""")
    payload = [dict(zip(('id', 'arch_db', 'name', 'website_meta_title',
                        'website_meta_description', 'website_meta_og_img'), row))
               for row in cr.fetchall()]
    cr.execute("""INSERT INTO ir_config_parameter (key,value) VALUES (%s,%s)
                  ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value""", (KEY, json.dumps(payload)))
