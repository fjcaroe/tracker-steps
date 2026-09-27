"""Publish the Exportaciones card in generic and website-specific views."""

from pathlib import Path

from lxml import etree
from odoo import SUPERUSER_ID, api


def _record_values(path, record_id):
    record = etree.parse(str(path)).xpath(f"//record[@id='{record_id}']")[0]
    values = {
        "arch_db": etree.tostring(record.find("field[@name='arch']")[0], encoding="unicode"),
    }
    for field in record.findall("field"):
        if field.get("name") in {
            "name", "website_meta_title", "website_meta_description", "website_meta_og_img"
        }:
            values[field.get("name")] = field.text
    return values


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    root = Path(__file__).resolve().parents[2] / "views"
    for record_id, filename in (
        ("website.homepage", "homepage.xml"),
        ("step_demo_homepage.solution_logistica_view", "solution_pages.xml"),
    ):
        source = env.ref(record_id, raise_if_not_found=False)
        if not source:
            continue
        values = _record_values(root / filename, record_id.split(".")[-1])
        source.write(values)
        env["ir.ui.view"].search([
            ("key", "=", source.key),
            ("id", "!=", source.id),
            ("inherit_id", "=", False),
            ("active", "=", True),
        ]).write(values)
