"""Pre-migración a 18.0.2.0.0.

Deduplica ``step_management_budget_center`` por ``(budget_id, center_id)`` antes
de que se cree la restricción SQL ``budget_center_uniq``. Idempotente: si no hay
duplicados no hace nada. Si los duplicados difieren en datos relevantes
(``hectares`` / ``notes``) aborta para revisión manual: no se descarta
información silenciosamente.

Sin ``commit()`` manual, sin IDs numéricos hardcodeados.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT budget_id, center_id, array_agg(id ORDER BY id) AS ids
        FROM step_management_budget_center
        WHERE budget_id IS NOT NULL AND center_id IS NOT NULL
        GROUP BY budget_id, center_id
        HAVING count(*) > 1
    """)
    duplicates = cr.fetchall()
    if not duplicates:
        _logger.info("step_management_costs 18.0.2.0.0: sin centros de presupuesto duplicados.")
        return

    conflicting = []
    removable = []
    for _budget_id, _center_id, ids in duplicates:
        keep, rest = ids[0], ids[1:]
        cr.execute("""
            SELECT id, hectares, coalesce(notes, '')
            FROM step_management_budget_center
            WHERE id = ANY(%s)
        """, (ids,))
        rows = {row[0]: (round(row[1] or 0.0, 4), row[2]) for row in cr.fetchall()}
        reference = rows[keep]
        if any(rows[other] != reference for other in rest):
            conflicting.append((keep, rest, rows))
        else:
            removable.extend(rest)

    if conflicting:
        detail = "\n".join(
            "  budget_center id=%s conserva; difieren %s (%s)" % (keep, rest, rows)
            for keep, rest, rows in conflicting
        )
        raise Exception(
            "step_management_costs 18.0.2.0.0: hay centros de presupuesto "
            "duplicados con datos distintos. Resuélvalos manualmente antes de "
            "actualizar:\n%s" % detail
        )

    cr.execute(
        "DELETE FROM step_management_budget_center WHERE id = ANY(%s)", (removable,)
    )
    _logger.info(
        "step_management_costs 18.0.2.0.0: eliminados %s centros de presupuesto "
        "duplicados idénticos.", len(removable),
    )
