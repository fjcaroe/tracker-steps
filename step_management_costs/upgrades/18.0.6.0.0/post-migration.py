"""Initialize calculation modes and recompute auditable monthly totals."""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE step_management_budget_line
           SET calculation_mode = 'quantity'
         WHERE calculation_mode IS NULL
    """)
    _logger.info(
        "18.0.6.0.0: calculation_mode inicializado en %s líneas.", cr.rowcount
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    months = env["step.management.budget.month"].search([])
    if months:
        months._recompute_recordset(["amount"])
    lines = env["step.management.budget.line"].search([])
    if lines:
        lines._recompute_recordset([
            "amount", "monthly_quantity", "monthly_amount", "distribution_complete",
        ])
    _logger.info(
        "18.0.6.0.0: recalculadas %s líneas y %s distribuciones mensuales.",
        len(lines), len(months),
    )
