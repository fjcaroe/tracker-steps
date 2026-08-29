import uuid

from . import models
from . import controllers


def post_init_hook(env):
    """Backfill campos UUID únicos para registros que ya existían antes de
    instalar el addon.

    Odoo respalda columnas nuevas con `default=<callable>` haciendo UN solo
    UPDATE masivo con un único valor calculado, no una llamada por fila — así
    que todo registro preexistente termina con el MISMO uuid duplicado (y el
    constraint unique() de la tabla no llega a crearse). Por eso no basta con
    buscar `campo = False`: hay que reasignar explícitamente, uno por uno,
    cualquier registro que quedó con ese valor compartido."""
    for model_name, field_name in [
        ('hr.employee', 'mobile_credential_uuid'),
        ('step.movi.registry', 'uuid'),
    ]:
        Model = env[model_name].sudo()
        records = Model.search([])
        seen = set()
        for record in records:
            value = record[field_name]
            if not value or value in seen:
                record[field_name] = str(uuid.uuid4())
            else:
                seen.add(value)
