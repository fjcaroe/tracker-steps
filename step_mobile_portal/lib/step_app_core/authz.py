"""Reglas de autorización: vigencia de membresías y concesiones, permisos efectivos y política offline.

Todo recibe datos simples (diccionarios) para poder probarse sin Odoo. Las fechas son `datetime` ingenuos en UTC.
"""
from datetime import datetime, timedelta

ACTIVE = 'active'
DEFAULT_OFFLINE_HOURS = 72


def _in_window(row, at: datetime) -> bool:
    start, end = row.get('valid_from'), row.get('valid_to')
    return (start is None or start <= at) and (end is None or at < end)


def membership_active_at(membership: dict, at: datetime) -> bool:
    return membership.get('state') == ACTIVE and _in_window(membership, at)


def grant_active_at(grant: dict, at: datetime) -> bool:
    """Una concesión vale en `at` si estaba en vigencia y no se había revocado todavía."""
    revoked = grant.get('revoked_at')
    if revoked is not None and revoked <= at:
        return False
    return _in_window(grant, at)


def effective_permissions(membership: dict, grants, role_permissions: dict, at: datetime) -> set:
    """Permisos vigentes de una membresía. `role_permissions` mapea (módulo, rol) -> lista de permisos."""
    if not membership_active_at(membership, at):
        return set()
    result = set()
    for grant in grants:
        if grant['membership_id'] == membership['id'] and grant_active_at(grant, at):
            result.update(role_permissions.get((grant['module'], grant['role']), ()))
    return result


def enabled_modules(membership: dict, grants, installed: set, at: datetime) -> list:
    """Módulos con alguna concesión vigente que además están instalados y compatibles en el servidor."""
    if not membership_active_at(membership, at):
        return []
    seen = []
    for grant in grants:
        if (grant['membership_id'] == membership['id'] and grant_active_at(grant, at)
                and grant['module'] in installed and grant['module'] not in seen):
            seen.append(grant['module'])
    return seen


def scope_allows(grant: dict, resource_id) -> bool:
    """Una concesión con alcance (lista de IDs) solo cubre esos recursos; sin alcance cubre todos los de la empresa."""
    scope = grant.get('scope_ids')
    return not scope or resource_id in scope


def offline_until(validated_at: datetime, hours: int = DEFAULT_OFFLINE_HOURS) -> datetime:
    return validated_at + timedelta(hours=max(0, int(hours)))


def offline_allowed(now: datetime, until) -> bool:
    return until is not None and now < until


def event_acceptable(captured_at: datetime, grants, module: str, role: str, access_ended_at=None, resource_id=None):
    """Política del servidor para eventos capturados sin conexión.

    Se acepta si una concesión (módulo+rol) estaba vigente en el instante de captura, cubría el recurso (si lo hay) y el
    acceso de la persona a la empresa no había terminado todavía, aunque hoy esté revocado o suspendido.
    Devuelve (aceptado, motivo).
    """
    if access_ended_at is not None and captured_at >= access_ended_at:
        return False, 'access_ended_before_capture'
    candidates = [g for g in grants if g['module'] == module and g['role'] == role]
    if not candidates:
        return False, 'no_grant'
    valid = [g for g in candidates if grant_active_at(g, captured_at)]
    if not valid:
        return False, 'grant_not_valid_at_capture'
    if resource_id is not None and not any(scope_allows(g, resource_id) for g in valid):
        return False, 'resource_out_of_scope'
    return True, 'ok'
