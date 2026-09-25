"""Pre-migration checks for 18.0.6.0.0.

The SQL uniqueness constraint for months must never discard or merge business
data silently. Existing duplicates abort the upgrade with actionable IDs.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT budget_line_id, month, array_agg(id ORDER BY id)
          FROM step_management_budget_month
         WHERE budget_line_id IS NOT NULL AND month IS NOT NULL
      GROUP BY budget_line_id, month
        HAVING count(*) > 1
      ORDER BY budget_line_id, month
    """)
    duplicates = cr.fetchall()
    if duplicates:
        detail = "; ".join(
            "line=%s month=%s ids=%s" % row for row in duplicates[:50]
        )
        raise Exception(
            "step_management_costs 18.0.6.0.0: existen meses duplicados. "
            "Resuélvalos manualmente antes de actualizar: %s" % detail
        )
    _logger.info("18.0.6.0.0: no hay meses duplicados por línea.")
