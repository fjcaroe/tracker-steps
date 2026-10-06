"""T51 — el centro de costo ahora es la cuenta analítica.

Completa, sin sobrescribir valores ya informados, los campos de gestión de la
cuenta analítica (`farm`, `species`, `variety`, `hectares`, `plants`,
`cost_type`) desde los maestros agrícolas reales de `step_hr`. Reejecutable.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT count(*) FROM information_schema.columns
         WHERE table_name = 'account_analytic_account'
           AND column_name IN ('fundo_id', 'farm')
    """)
    if cr.fetchone()[0] < 2:
        return

    for core_field, master_table, master_field in (
        ("farm", "step_fundo", "fundo_id"),
        ("species", "step_especie", "especie_id"),
        ("variety", "step_variedad", "variedad_id"),
    ):
        cr.execute("""
            UPDATE account_analytic_account a
               SET %(core_field)s = m.name
              FROM %(master_table)s m
             WHERE m.id = a.%(master_field)s
               AND (a.%(core_field)s IS NULL OR a.%(core_field)s = '')
        """ % {"core_field": core_field, "master_table": master_table,
               "master_field": master_field})
    cr.execute("""
        UPDATE account_analytic_account
           SET hectares = has_cost
         WHERE has_cost > 0 AND (hectares IS NULL OR hectares = 0)
    """)
    cr.execute("""
        UPDATE account_analytic_account
           SET plants = plant_cost
         WHERE plant_cost > 0 AND (plants IS NULL OR plants = 0)
    """)
    cr.execute("""
        UPDATE account_analytic_account
           SET cost_type = CASE type_costo
                 WHEN 'fruta' THEN 'crop' WHEN 'cultivo' THEN 'crop'
                 WHEN 'maquinaria' THEN 'machinery'
                 WHEN 'operacional' THEN 'operational'
                 WHEN 'admin' THEN 'administrative' END
         WHERE cost_type IS NULL AND type_costo IS NOT NULL
    """)
    _logger.info("puente agrícola 18.0.2.0.0: campos de gestión de la cuenta analítica completados.")
