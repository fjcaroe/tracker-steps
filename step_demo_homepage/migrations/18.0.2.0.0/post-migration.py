from pathlib import Path

from lxml import etree
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Refresh website-specific primary copies created by the website editor."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    homepage = env.ref("website.homepage", raise_if_not_found=False)
    if not homepage:
        return
    # website.homepage may be marked noupdate by its original owning module.
    # Keep the XML as the source of truth without changing that metadata.
    source = etree.parse(str(Path(__file__).resolve().parents[2] / "views/homepage.xml"))
    record = source.xpath("//record[@id='website.homepage']")[0]
    homepage.write({
        "name": record.find("field[@name='name']").text,
        "arch_db": etree.tostring(record.find("field[@name='arch']")[0], encoding="unicode"),
    })
    copies = env["ir.ui.view"].search([
        ("key", "=", "website.homepage"),
        ("id", "!=", homepage.id),
        ("inherit_id", "=", False),
        ("active", "=", True),
        ("name", "ilike", "Steps"),
    ])
    copies.write({"name": homepage.name, "arch_db": homepage.arch_db})
