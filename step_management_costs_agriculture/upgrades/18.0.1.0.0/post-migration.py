"""Puente agrícola — primera instalación (`18.0.1.0.0`).

Backfill no destructivo: para un `step.management.cost.center` ya enlazado
a una cuenta analítica real (`analytic_account_id`, dato explícito, nunca
inferido por texto) cuyo `farm`/`species`/`variety` (Char del núcleo)
estén **vacíos**, copia el nombre del maestro real correspondiente
(`fundo_id`/`especie_id`/`variedad_id`). Nunca sobrescribe un valor ya
informado — no hay ambigüedad posible porque la relación (`analytic_account_id`)
ya es explícita y única; no se trata de un emparejamiento por texto.
Reejecutable sin efecto (sólo toca filas con el campo aún vacío).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT count(*) FROM information_schema.columns
         WHERE table_name = 'account_analytic_account' AND column_name = 'fundo_id'
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "puente agrícola: la cuenta analítica no tiene campos agrícolas "
            "(¿step_hr desactualizado?); nada que enriquecer."
        )
        return

    updated = {"farm": 0, "species": 0, "variety": 0}
    for core_field, master_table, master_field in (
        ("farm", "step_fundo", "fundo_id"),
        ("species", "step_especie", "especie_id"),
        ("variety", "step_variedad", "variedad_id"),
    ):
        cr.execute("""
            UPDATE step_management_cost_center c
               SET %(core_field)s = m.name
              FROM account_analytic_account a
              JOIN %(master_table)s m ON m.id = a.%(master_field)s
             WHERE c.analytic_account_id = a.id
               AND (c.%(core_field)s IS NULL OR c.%(core_field)s = '')
               AND a.%(master_field)s IS NOT NULL
        """ % {
            "core_field": core_field, "master_table": master_table,
            "master_field": master_field,
        })
        updated[core_field] = cr.rowcount

    _logger.info(
        "puente agrícola 18.0.1.0.0: enriquecidos %(farm)s fundo(s), "
        "%(species)s especie(s), %(variety)s variedad(es) desde el maestro "
        "real (sólo donde el campo del núcleo estaba vacío).",
        updated,
    )
