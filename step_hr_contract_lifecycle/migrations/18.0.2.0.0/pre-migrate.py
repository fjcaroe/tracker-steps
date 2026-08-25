# -*- coding: utf-8 -*-
"""Pre-migración 18.0.1.0.0 -> 18.0.2.0.0.

Esta versión separa el núcleo de todo motor de nómina específico. El
único cambio de esquema relevante es que ``hr.contract.fundo_id`` deja
de ser declarado por este módulo (pasa al adaptador agrícola). Odoo NO
elimina la columna física al quitar la declaración de un campo: queda
huérfana hasta que el adaptador la vuelva a declarar con el mismo
nombre/tipo, momento en el que la adopta sin pérdida de datos. Este
script sólo registra el estado antes de migrar, para poder comparar
después (Fase 2.7: "registrar conteos antes/después").
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "select column_name from information_schema.columns "
        "where table_name = 'hr_contract' and column_name = 'fundo_id'"
    )
    has_fundo_column = bool(cr.fetchone())
    fundo_count = 0
    if has_fundo_column:
        cr.execute("select count(*) from hr_contract where fundo_id is not null")
        fundo_count = cr.fetchone()[0]

    cr.execute("select count(*) from hr_contract")
    contract_count = cr.fetchone()[0]

    for table in ("hr_termination_notice", "hr_severance", "hr_labor_document"):
        cr.execute(
            "select 1 from information_schema.tables where table_name = %s", (table,)
        )
        if not cr.fetchone():
            continue
        cr.execute("select count(*) from %s" % table)  # noqa: S608 - nombre fijo, no input externo
        _logger.info("PRE-MIGRACIÓN 18.0.2.0.0: %s tiene %s filas.", table, cr.fetchone()[0])

    _logger.info(
        "PRE-MIGRACIÓN 18.0.2.0.0: hr_contract=%s filas, "
        "fundo_id column=%s, contratos con fundo_id set=%s.",
        contract_count, has_fundo_column, fundo_count,
    )
