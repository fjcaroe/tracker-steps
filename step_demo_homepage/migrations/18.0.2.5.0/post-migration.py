"""Publish the commercial homepage, including active website-specific copies."""
from pathlib import Path

from lxml import etree
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    document = etree.parse(str(Path(__file__).resolve().parents[2] / "views/homepage.xml"))
    for xml_id in ("website.homepage", "step_demo_homepage.nav", "step_demo_homepage.footer"):
        record_id = xml_id if xml_id == "website.homepage" else xml_id.split(".")[1]
        record = document.xpath("//record[@id=$record_id]", record_id=record_id)[0]
        source = env.ref(xml_id)
        values = {"arch_db": etree.tostring(record.find("field[@name='arch']")[0], encoding="unicode")}
        for field in record.findall("field"):
            if field.get("name") in {"name", "website_meta_title", "website_meta_description", "website_meta_og_img"}:
                values[field.get("name")] = field.text
        source.write(values)
        env["ir.ui.view"].search([
            ("key", "=", source.key), ("id", "!=", source.id),
            ("inherit_id", "=", False), ("active", "=", True),
        ]).write(values)
