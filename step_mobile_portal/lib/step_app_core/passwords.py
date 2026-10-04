"""Contraseñas con scrypt (biblioteca estándar) y política mínima."""
import base64
import hashlib
import hmac
import os
import re

_N, _R, _P = 2 ** 14, 8, 1
MIN_LENGTH = 10
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def normalize_email(email) -> str:
    return (email or '').strip().lower()


def valid_email(email) -> bool:
    return bool(_EMAIL_RE.match(normalize_email(email))) and len(email) <= 254


def password_problem(password, email=None):
    """Devuelve el motivo por el que la contraseña no sirve, o None."""
    if not isinstance(password, str) or len(password) < MIN_LENGTH:
        return 'too_short'
    if len(password) > 256:
        return 'too_long'
    if email and password.strip().lower() == normalize_email(email):
        return 'same_as_email'
    if len(set(password)) < 4:
        return 'too_simple'
    return None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    b64 = lambda raw: base64.b64encode(raw).decode()
    return 'scrypt$%d$%d$%d$%s$%s' % (_N, _R, _P, b64(salt), b64(digest))


_DUMMY = hash_password('contraseña-de-relleno-para-igualar-tiempos')


def verify_password(password, stored) -> bool:
    """Compara en tiempo constante; con `stored` vacío gasta el mismo tiempo para no revelar si la cuenta existe."""
    candidate = stored or _DUMMY
    try:
        scheme, n, r, p, salt, digest = candidate.split('$')
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt((password or '').encode(), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return bool(stored) and scheme == 'scrypt' and hmac.compare_digest(actual, expected)
