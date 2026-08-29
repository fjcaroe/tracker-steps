"""Adopt legacy Studio BPA folios without deleting historical data."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Usage = env["step.hrs.machinery"].with_context(active_test=False)
    if "x_studio_folio_bpa" not in Usage._fields:
        return
    Application = env["x_aplicacion_foliar"].with_context(active_test=False)
    for usage in Usage.search([("bpa_order_id", "=", False), ("x_studio_folio_bpa", "!=", False)]):
        folio = usage.x_studio_folio_bpa.strip()
        if not folio:
            continue
        application = Application.search([
            ("company_id", "=", usage.company_id.id),
            "|", ("x_studio_nmero_ot_bpa", "=", folio), ("x_name", "=", folio),
        ], limit=1)
        if application:
            usage.bpa_order_id = application
