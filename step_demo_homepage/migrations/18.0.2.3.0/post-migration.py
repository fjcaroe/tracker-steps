from pathlib import Path

from lxml import etree
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Refresh the branded homepage after the SEO pass (og:image, hero
    picture/srcset, area links) — same per-website copy issue as prior
    homepage updates: the XML data reload only touches the generic
    website.homepage view, not the per-website copies actually served."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    homepage = env.ref("website.homepage", raise_if_not_found=False)
    if not homepage:
        return

    source = etree.parse(
        str(Path(__file__).resolve().parents[2] / "views/homepage.xml")
    )
    record = source.xpath("//record[@id='website.homepage']")[0]
    values = {
        field_name: record.find(f"field[@name='{field_name}']").text
        for field_name in (
            "name",
            "website_meta_title",
            "website_meta_description",
            "website_meta_og_img",
        )
    }
    values["arch_db"] = etree.tostring(
        record.find("field[@name='arch']")[0], encoding="unicode"
    )
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
