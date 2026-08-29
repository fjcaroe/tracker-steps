"""Inicializa una sola vez la clasificación Previred de jornadas existentes."""


def migrate(cr, version):
    # Esta migración pertenece al release que crea el campo. Su resultado es
    # determinista e idempotente; futuras elecciones manuales no se alteran
    # porque Odoo no vuelve a ejecutar una migración ya aplicada.
    cr.execute("""
        UPDATE resource_calendar
           SET previred_workday_type = CASE
                 WHEN COALESCE(hours_per_week, full_time_required_hours, 0)
                      BETWEEN 0.01 AND 30
                 THEN '2'
                 ELSE '1'
               END
    """)
