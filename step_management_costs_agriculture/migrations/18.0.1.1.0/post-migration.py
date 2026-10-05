import logging
from odoo import api, SUPERUSER_ID
from odoo.addons.step_management_costs_agriculture.models.estimation_catalog import backfill_catalog_links


def migrate(cr, version):
    if version:
        counts = backfill_catalog_links(api.Environment(cr, SUPERUSER_ID, {}))
        logging.getLogger(__name__).info("T50 linked existing estimation catalogs: %s", counts)
