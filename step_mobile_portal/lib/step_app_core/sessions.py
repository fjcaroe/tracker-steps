"""Sesiones con renovación rotatoria y detección de reutilización."""
from datetime import datetime, timedelta

from . import tokens

ACCESS_MINUTES = 30
REFRESH_DAYS = 30

OK, EXPIRED, REUSED, REVOKED, UNKNOWN = 'ok', 'expired', 'reused', 'revoked', 'unknown'


def issue(now: datetime, access_minutes: int = ACCESS_MINUTES, refresh_days: int = REFRESH_DAYS) -> dict:
    """Crea un par de tokens. Los valores en claro se entregan una sola vez; solo se guardan las huellas."""
    access, refresh = tokens.new_token(), tokens.new_token()
    return {
        'access': access, 'refresh': refresh,
        'access_hash': tokens.hash_token(access), 'refresh_hash': tokens.hash_token(refresh),
        'access_expires_at': now + timedelta(minutes=access_minutes),
        'refresh_expires_at': now + timedelta(days=refresh_days),
    }


def classify_access(record, presented: str, now: datetime) -> str:
    if not record or not tokens.verify_token(presented, record.get('access_hash')):
        return UNKNOWN
    if record.get('revoked_at'):
        return REVOKED
    return EXPIRED if now >= record['access_expires_at'] else OK


def classify_refresh(record, presented: str, now: datetime) -> str:
    """`record` es la sesión encontrada por la huella presentada (actual o anterior). Un refresh ya usado revoca la familia."""
    if not record:
        return UNKNOWN
    if record.get('revoked_at'):
        return REVOKED
    if tokens.verify_token(presented, record.get('previous_refresh_hash')):
        return REUSED
    if not tokens.verify_token(presented, record.get('refresh_hash')):
        return UNKNOWN
    return EXPIRED if now >= record['refresh_expires_at'] else OK
