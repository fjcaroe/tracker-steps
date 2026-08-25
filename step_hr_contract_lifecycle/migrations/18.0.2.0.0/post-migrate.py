# -*- coding: utf-8 -*-
"""Post-migración 18.0.1.0.0 -> 18.0.2.0.0.

Confirma que la columna ``hr_contract.fundo_id`` y sus datos siguen
presentes después de que el núcleo dejó de declararla (persiste como
columna huérfana hasta que el adaptador agrícola la reclame). No aborta
el arranque si el adaptador todavía no está instalado (ej. Demo-SyS):
sólo lo registra."""
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

    _logger.info(
        "POST-MIGRACIÓN 18.0.2.0.0: hr_contract=%s filas, "
        "fundo_id column=%s (huérfana hasta instalar el adaptador "
        "agrícola), contratos con fundo_id set=%s (deben coincidir con "
        "el conteo de PRE-MIGRACIÓN).",
        contract_count, has_fundo_column, fundo_count,
    )
