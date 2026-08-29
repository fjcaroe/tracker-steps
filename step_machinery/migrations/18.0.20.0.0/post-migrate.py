# -*- coding: utf-8 -*-
"""Normaliza la identidad de los registros de Horas Máquina.

La migración es idempotente: puede ejecutarse varias veces sin duplicar
correlativos, sin perder nombres históricos y sin borrar ningún registro.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OT_SEQUENCE_CODE = "step.hrs.machinery.ot"
LEGACY_FOLIO_FIELD = "x_studio_folio_bpa"


def _preserve_legacy_names(cr):
    """Conserva el nombre anterior antes de recomponerlo."""
    cr.execute(
        """
        UPDATE step_hrs_machinery
           SET legacy_name = name
         WHERE legacy_name IS NULL
           AND name IS NOT NULL
           AND btrim(name) <> ''
        """
    )
    return cr.rowcount


def _assign_ot_numbers(cr):
    """Asigna el Número OT a los registros antiguos de forma determinística.

    Orden: empresa, luego fecha y luego id. El contador arranca sobre el mayor
    número ya existente, de modo que una segunda ejecución no reasigne nada ni
    choque con números futuros.
    """
    cr.execute(
        "SELECT COALESCE(MAX(ot_number::bigint), 0) FROM step_hrs_machinery "
        "WHERE ot_number ~ '^[0-9]+$'"
    )
    counter = cr.fetchone()[0]
    cr.execute(
        """
        SELECT id FROM step_hrs_machinery
         WHERE ot_number IS NULL OR btrim(ot_number) = ''
         ORDER BY company_id, date NULLS FIRST, id
        """
    )
    pending = [row[0] for row in cr.fetchall()]
    for record_id in pending:
        counter += 1
        cr.execute(
            "UPDATE step_hrs_machinery SET ot_number = %s WHERE id = %s",
            (str(counter), record_id),
        )
    return len(pending), counter


def _advance_sequences(env, highest):
    """Deja la secuencia por encima del mayor número ya asignado."""
    sequences = env["ir.sequence"].sudo().with_context(active_test=False).search(
        [("code", "=", OT_SEQUENCE_CODE)]
    )
    for sequence in sequences:
        if sequence.number_next_actual <= highest:
            sequence.write({"number_next_actual": highest + 1})
    return len(sequences)


def _archive_studio_folio_view(env):
    """Retira la personalización Studio que anteponía "Folio BPA" al formulario.

    Sólo se archiva (nunca se borra) y únicamente si el campo Studio no guarda
    datos, para no ocultar información existente.
    """
    Usage = env["step.hrs.machinery"]
    if LEGACY_FOLIO_FIELD in Usage._fields:
        env.cr.execute(
            "SELECT COUNT(*) FROM step_hrs_machinery WHERE COALESCE(%s, '') <> ''"
            % LEGACY_FOLIO_FIELD
        )
        if env.cr.fetchone()[0]:
            _logger.warning(
                "Maquinaria: %s conserva datos; la vista Studio no se archiva.",
                LEGACY_FOLIO_FIELD,
            )
            return 0
    views = env["ir.ui.view"].sudo().with_context(active_test=False).search([
        ("model", "=", "step.hrs.machinery"),
        ("mode", "=", "extension"),
        ("active", "=", True),
    ])
    archived = 0
    for view in views:
        if LEGACY_FOLIO_FIELD in (view.arch_db or ""):
            view.write({"active": False})
            archived += 1
            _logger.info("Maquinaria: vista Studio %s archivada (id=%s).", view.name, view.id)
    return archived


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Usage = env["step.hrs.machinery"].with_context(active_test=False)
    # El script trabaja en SQL directo: primero baja a base cualquier escritura
    # ORM pendiente para no leer valores desactualizados.
    env.flush_all()

    cr.execute("SELECT COUNT(*) FROM step_hrs_machinery")
    headers_before = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM step_hrs_machinery_line")
    lines_before = cr.fetchone()[0]
    _logger.info(
        "Maquinaria 18.0.20.0.0: antes -> %s encabezados, %s líneas.",
        headers_before, lines_before,
    )

    preserved = _preserve_legacy_names(cr)
    assigned, highest = _assign_ot_numbers(cr)
    env.invalidate_all()
    sequences = _advance_sequences(env, highest)
    archived = _archive_studio_folio_view(env)

    env.invalidate_all()
    # Los registros costeados o contabilizados conservan su identidad histórica.
    renamed = Usage.search([
        ("state", "not in", ("costed", "accounted")),
        ("invoice_id", "=", False),
    ])
    renamed._sync_composed_name()

    cr.execute("SELECT COUNT(*) FROM step_hrs_machinery")
    headers_after = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM step_hrs_machinery_line")
    lines_after = cr.fetchone()[0]
    _logger.info(
        "Maquinaria 18.0.20.0.0: después -> %s encabezados, %s líneas. "
        "Nombres históricos preservados=%s, Números OT asignados=%s (máximo=%s), "
        "secuencias ajustadas=%s, vistas Studio archivadas=%s, nombres recompuestos=%s.",
        headers_after, lines_after, preserved, assigned, highest,
        sequences, archived, len(renamed),
    )
