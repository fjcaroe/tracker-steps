"""Reemplazo controlado de los perfiles semilla.

La versión 2.0.0 permitía describir un origen externo con `model_name`,
`model_domain` y `amount_field` escritos desde la interfaz. Esa superficie
desaparece: los orígenes externos pasan a ser adaptadores registrados en
código. Además, el mapeo semilla de SimpleDigital se corrigió tras verificarlo
contra una base con el motor del proveedor instalado.

Los perfiles semilla llevan `noupdate="1"` para no pisar ajustes del cliente,
así que la única manera limpia de corregirlos es eliminarlos ANTES de que el
cargador de datos vuelva a crearlos durante esta actualización. Se conserva la
asignación por empresa —que sí es una decisión del cliente— y se restaura en
`post-migrate` buscando el perfil por su código técnico.

Los perfiles creados a mano por el cliente NO se tocan: si alguna de sus
líneas usaba el mecanismo eliminado, `post-migrate` la marca y deja el perfil
en borrador con un mensaje accionable.
"""

import logging

_logger = logging.getLogger(__name__)

SEED_XML_IDS = (
    ("step_hr_remuneration_book", "profile_l10n_cl_extended"),
    ("step_hr_remuneration_book", "profile_simpledigital"),
)


def migrate(cr, version):
    if not version:
        return

    # 1. Recordar qué empresa tenía asignado cada perfil semilla.
    cr.execute(
        """
        SELECT c.id, p.code
          FROM res_company c
          JOIN step_remuneration_book_profile p
            ON p.id = c.remuneration_book_profile_id
        """
    )
    assignments = cr.fetchall()
    if assignments:
        cr.execute(
            """
            CREATE TABLE IF NOT EXISTS step_remuneration_book_profile_migration (
                company_id integer PRIMARY KEY,
                profile_code varchar
            )
            """
        )
        cr.execute("DELETE FROM step_remuneration_book_profile_migration")
        cr.executemany(
            "INSERT INTO step_remuneration_book_profile_migration "
            "(company_id, profile_code) VALUES (%s, %s)",
            assignments,
        )
        _logger.info(
            "Libro de Remuneraciones: se conservan %s asignaciones de perfil "
            "por empresa durante la migración.", len(assignments))

    # 2. Eliminar los perfiles semilla para que el cargador los recree con el
    #    mapeo corregido. Las líneas caen con `ondelete='cascade'`.
    for module, name in SEED_XML_IDS:
        cr.execute(
            "SELECT res_id FROM ir_model_data "
            "WHERE module = %s AND name = %s AND model = %s",
            (module, name, "step.remuneration.book.profile"),
        )
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            "DELETE FROM step_remuneration_book_profile WHERE id = %s",
            (row[0],),
        )
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (module, name),
        )
        _logger.info(
            "Libro de Remuneraciones: perfil semilla %s.%s eliminado para "
            "recrearse con el mapeo verificado.", module, name)
