import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Migración idempotente: copia las causales de hr.causal.termino
    hacia step.hr.termination.cause, sin borrar ni modificar el maestro
    original. Puede ejecutarse nuevamente (ej. al actualizar el módulo)
    sin producir duplicados: se salta cualquier causal ya migrada
    (origin_model + origin_id) y cualquier código ya existente."""
    Cause = env["step.hr.termination.cause"]
    if "hr.causal.termino" not in env:
        return
    Legacy = env["hr.causal.termino"]
    legacy_causes = Legacy.with_context(active_test=False).search([])
    before_count = Cause.search_count([])
    migrated = 0
    skipped = 0
    for legacy in legacy_causes:
        existing = Cause.search(
            [("origin_model", "=", "hr.causal.termino"), ("origin_id", "=", legacy.id)],
            limit=1,
        )
        if existing:
            skipped += 1
            continue
        code = legacy.codigo or str(legacy.id)
        if Cause.search([("code", "=", code)], limit=1):
            code = "hr_causal_termino_%s" % legacy.id
        # Compatibilidad con dos posibles orígenes de estos datos:
        # campos Studio nativos de hr.causal.termino (x_studio_*), o los
        # campos que una versión anterior de este mismo addon pudo haber
        # agregado a hr.causal.termino (sin ese prefijo). Se leen ambos
        # con getattr para no perder información real ya cargada.
        ias_anual = getattr(legacy, "applies_ias_anual", None)
        if ias_anual is None:
            ias_anual = getattr(legacy, "x_studio_ias_anual", False)
        ias_mensual = getattr(legacy, "applies_ias_mensual", None)
        if ias_mensual is None:
            ias_mensual = getattr(legacy, "x_studio_ias_mes", False)
        mes_aviso = getattr(legacy, "applies_mes_aviso", None)
        if mes_aviso is None:
            mes_aviso = getattr(legacy, "x_studio_base_mes_aviso", False)
        dt_code = getattr(legacy, "dt_codigo_causal", None)
        Cause.create(
            {
                "name": legacy.name or code,
                "code": code,
                "dt_code": str(dt_code) if dt_code else code,
                "articulo": getattr(legacy, "articulo", False) or "",
                "description_legal": getattr(legacy, "description_legal", False) or "",
                "date_from": getattr(legacy, "date_from", False) or False,
                "date_to": getattr(legacy, "date_to", False) or False,
                "requires_certificate": getattr(legacy, "requires_certificate", False) or False,
                "applies_ias_anual": bool(ias_anual),
                "applies_ias_mensual": bool(ias_mensual),
                "applies_mes_aviso": bool(mes_aviso),
                "active": getattr(legacy, "active", True),
                "origin_model": "hr.causal.termino",
                "origin_id": legacy.id,
            }
        )
        migrated += 1
    after_count = Cause.search_count([])
    _logger.info(
        "Migración causales hr.causal.termino -> step.hr.termination.cause: "
        "%s migradas, %s ya existían (omitidas). Conteo "
        "step.hr.termination.cause: %s -> %s.",
        migrated, skipped, before_count, after_count,
    )
