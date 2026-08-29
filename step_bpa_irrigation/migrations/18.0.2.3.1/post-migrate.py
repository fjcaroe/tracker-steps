# -*- coding: utf-8 -*-
"""Libera restricciones NOT NULL huérfanas en las tablas BPA.

STEPS_DEMO arrastraba un `NOT NULL` en `x_aplicacion_foliar.x_studio_consumo_lt_x_hora`
creado en su día por Studio. El campo no es obligatorio en el modelo, así que la
restricción sólo impedía crear OT-BPA (desde la interfaz y por RPC).

La pasada es idempotente y conservadora: sólo suelta columnas cuya definición
Python NO es obligatoria, nunca borra datos ni toca columnas requeridas.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BPA_MODELS = (
    "x_aplicacion_foliar",
    "x_riego_y_fertilizacio",
    "x_monitoreo_agricola",
    "x_sector_de_riego",
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    relaxed = []
    for model_name in BPA_MODELS:
        model = env.get(model_name)
        if model is None:
            continue
        table = model._table
        cr.execute(
            """
            SELECT column_name FROM information_schema.columns
             WHERE table_name = %s AND is_nullable = 'NO' AND column_name <> 'id'
            """,
            (table,),
        )
        for (column,) in cr.fetchall():
            field = model._fields.get(column)
            if field is not None and field.required:
                continue
            cr.execute(
                'ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (table, column))
            relaxed.append("%s.%s" % (table, column))
    _logger.info(
        "BPA 18.0.2.3.1: restricciones NOT NULL liberadas: %s",
        relaxed or "(ninguna, nada que corregir)",
    )
