from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Classify only shipped guides; preserve approved text and custom sources."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in ("start", "duplicate", "offline", "tariff"):
        article = env.ref("step_support_assistant.help_colaciones_" + xmlid,
                          raise_if_not_found=False)
        if article:
            article.write({"category": "colaciones", "sequence": 200})
    for xmlid, sequence in (("business_queries", 90), ("permissions", 170),
                            ("support_request", 180), ("assistant_scope", 190)):
        article = env.ref("step_support_assistant.help_" + xmlid, raise_if_not_found=False)
        if article:
            article.write({"sequence": sequence})
