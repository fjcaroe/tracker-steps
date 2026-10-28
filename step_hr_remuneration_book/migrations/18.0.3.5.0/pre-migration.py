from odoo import api, SUPERUSER_ID
from odoo.addons.step_hr_remuneration_book.hooks import ensure_engine_aliases


def migrate(cr, version):
    ensure_engine_aliases(api.Environment(cr, SUPERUSER_ID, {}))
