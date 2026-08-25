import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Migración idempotente: copia las causales de
    hr.causal.contract.end hacia step.hr.termination.cause, sin borrar
    ni modificar el maestro original. Reejecutable sin duplicados."""
    Cause = env["step.hr.termination.cause"]
    if "hr.causal.contract.end" not in env:
        return
    Legacy = env["hr.causal.contract.end"]
    legacy_causes = Legacy.with_context(active_test=False).search([])
    before_count = Cause.search_count([])
    migrated = 0
    skipped = 0
    for legacy in legacy_causes:
        existing = Cause.search(
            [
                ("origin_model", "=", "hr.causal.contract.end"),
                ("origin_id", "=", legacy.id),
            ],
            limit=1,
        )
        if existing:
            skipped += 1
            continue
        code = legacy.code or str(legacy.id)
        if Cause.search([("code", "=", code)], limit=1):
            code = "hr_causal_contract_end_%s" % legacy.id
        Cause.create(
            {
                "name": legacy.name or code,
                "code": code,
                # El código de SimpleDigital ya coincide con el código
                # numérico de la tabla "Causales de Despido" de la DT.
                "dt_code": legacy.code or code,
                "active": legacy.active,
                "origin_model": "hr.causal.contract.end",
                "origin_id": legacy.id,
            }
        )
        migrated += 1
    after_count = Cause.search_count([])
    _logger.info(
        "Migración causales hr.causal.contract.end -> "
        "step.hr.termination.cause: %s migradas, %s ya existían "
        "(omitidas). Conteo step.hr.termination.cause: %s -> %s.",
        migrated, skipped, before_count, after_count,
    )
