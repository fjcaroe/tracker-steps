# -*- coding: utf-8 -*-
"""Repara el bug detectado en la primera instalación real (Desarrollo,
2026-08-25): el `post_init_hook` original buscaba `campo = False` para
decidir a quién backfillear, pero Odoo ya había escrito a TODOS los
registros preexistentes el mismo valor de uuid en un solo UPDATE masivo (así
respalda `_auto_init` una columna nueva con `default=<callable>`), dejando
duplicados y sin poder crear el `unique()` de la tabla. Mismo arreglo que el
`post_init_hook` corregido, para las instalaciones que ya corrieron con la
versión con el bug."""

import logging
import uuid

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = _get_env(cr)
    for model_name, field_name in [
        ('hr.employee', 'mobile_credential_uuid'),
        ('step.movi.registry', 'uuid'),
    ]:
        if model_name not in env:
            continue
        Model = env[model_name].sudo()
        records = Model.search([])
        seen = set()
        fixed = 0
        for record in records:
            value = record[field_name]
            if not value or value in seen:
                record[field_name] = str(uuid.uuid4())
                fixed += 1
            else:
                seen.add(value)
        _logger.info("step_mobilization post-migrate: %s.%s deduplicados=%d de %d",
                     model_name, field_name, fixed, len(records))


def _get_env(cr):
    from odoo import api, SUPERUSER_ID
    return api.Environment(cr, SUPERUSER_ID, {})
