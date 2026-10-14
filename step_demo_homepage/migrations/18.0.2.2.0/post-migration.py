from pathlib import Path

from lxml import etree
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Refresh the branded homepage and its SEO metadata."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    homepage = env.ref("website.homepage", raise_if_not_found=False)
    if not homepage:
        return

    source = etree.parse(
        str(Path(__file__).resolve().parents[2] / "views/homepage.xml")
    )
    record = source.xpath("//record[@id='website.homepage']")[0]
    field_text = {
        field_name: record.find(f"field[@name='{field_name}']").text
        for field_name in (
            "name",
            "website_meta_title",
            "website_meta_description",
        )
    }
    values = {
        **field_text,
        "arch_db": etree.tostring(
            record.find("field[@name='arch']")[0], encoding="unicode"
        ),
    }
    homepage.write(values)

    copies = env["ir.ui.view"].search(
        [
            ("key", "=", "website.homepage"),
            ("id", "!=", homepage.id),
            ("inherit_id", "=", False),
            ("active", "=", True),
        ]
    )
    copies.write(values)

    websites = env["website"].sudo().search([])
    websites.write({"name": "Steps Agro"})
