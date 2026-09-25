"""Post-migración a 18.0.2.0.0.

- Puebla los ``company_id`` nuevos (related stored) en centros de presupuesto y
  en indicadores de plantilla.
- Inicializa ``revision`` = 1 donde falte.
- Marca los costos históricos previos como ``origin = 'unreviewed'`` para que no
  entren a los comparativos hasta que se clasifique su procedencia.
- Inventaría (log) los centros de costo sin cuenta analítica o con cuenta de
  otra empresa. No crea ni asigna cuentas: la elección es del operador.

Idempotente. Sin ``commit()`` manual, sin IDs numéricos hardcodeados.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1. company_id related-stored recién agregados.
    cr.execute("""
        UPDATE step_management_budget_center bc
        SET company_id = ob.company_id
        FROM step_management_operational_budget ob
        WHERE bc.budget_id = ob.id AND bc.company_id IS DISTINCT FROM ob.company_id
    """)
    _logger.info("18.0.2.0.0: company_id poblado en %s centros de presupuesto.", cr.rowcount)

    cr.execute("""
        UPDATE step_management_budget_template_line tl
        SET company_id = t.company_id
        FROM step_management_budget_template t
        WHERE tl.template_id = t.id AND tl.company_id IS DISTINCT FROM t.company_id
    """)
    _logger.info("18.0.2.0.0: company_id poblado en %s indicadores de plantilla.", cr.rowcount)

    # 2. revision por defecto.
    cr.execute("""
        UPDATE step_management_operational_budget
        SET revision = 1
        WHERE revision IS NULL OR revision = 0
    """)

    # 3. Costos históricos previos: procedencia sin clasificar.
    #    Todas las filas existentes preceden a esta versión.
    cr.execute("""
        UPDATE step_management_historical_cost
        SET origin = 'unreviewed'
        WHERE origin IS NULL OR origin = 'external'
    """)
    _logger.info(
        "18.0.2.0.0: %s costos históricos marcados como 'sin clasificar'. "
        "Revise su procedencia antes de incluirlos en comparativos.", cr.rowcount,
    )

    # 4. Inventario de cuentas analíticas de centro (solo informe).
    cr.execute("""
        SELECT cc.code, cc.name, cc.company_id, cc.analytic_account_id,
               aa.company_id AS account_company_id
        FROM step_management_cost_center cc
        LEFT JOIN account_analytic_account aa ON aa.id = cc.analytic_account_id
        WHERE cc.active
    """)
    missing, cross = [], []
    for code, name, company_id, account_id, account_company_id in cr.fetchall():
        if not account_id:
            missing.append("%s %s" % (code, name))
        elif account_company_id and account_company_id != company_id:
            cross.append("%s %s" % (code, name))
    if missing:
        _logger.warning(
            "18.0.2.0.0: %s centro(s) de costo activos SIN cuenta analítica. "
            "No podrán aprobar nuevos presupuestos hasta asignarla: %s",
            len(missing), "; ".join(missing),
        )
    if cross:
        _logger.warning(
            "18.0.2.0.0: %s centro(s) de costo con cuenta analítica de OTRA "
            "empresa. Corrija antes de aprobar: %s",
            len(cross), "; ".join(cross),
        )
    if not missing and not cross:
        _logger.info("18.0.2.0.0: todos los centros de costo activos tienen cuenta analítica coherente.")
