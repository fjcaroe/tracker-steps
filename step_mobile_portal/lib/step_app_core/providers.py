"""Validación en servidor de identidades externas. Nunca se confía en lo que dice el cliente."""
import base64
import json


class ProviderError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _default_google_verifier(token: str) -> dict:
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:  # pragma: no cover - depende del despliegue
        raise ProviderError('provider_not_configured') from exc
    try:
        # La biblioteca verifica firma, emisor y expiración; la audiencia se comprueba abajo contra la lista configurada.
        return id_token.verify_oauth2_token(token, google_requests.Request(), audience=None)
    except ValueError as exc:
        raise ProviderError('invalid_token') from exc
    except Exception as exc:  # TransportError al bajar los certificados de Google, etc.
        if type(exc).__name__ in ('TransportError', 'RefreshError'):
            raise ProviderError('provider_unavailable') from exc
        raise


def _looks_like_signed_jwt(token: str) -> bool:
    """Descarta basura antes de consultar a Google: un token mal formado no debe provocar una petición de red."""
    parts = token.split('.')
    if len(parts) != 3 or not all(parts) or len(token) > 8192:
        return False
    try:
        header = json.loads(base64.urlsafe_b64decode(parts[0] + '=' * (-len(parts[0]) % 4)))
    except (ValueError, TypeError):
        return False
    return isinstance(header, dict) and header.get('alg') == 'RS256' and bool(header.get('kid'))


def verify_google_id_token(token, client_ids, verifier=None) -> dict:
    """Devuelve {'subject', 'email', 'email_verified', 'name'} o lanza ProviderError."""
    client_ids = [c for c in (client_ids or []) if c]
    if not client_ids:
        raise ProviderError('provider_not_configured')
    if not isinstance(token, str) or not token:
        raise ProviderError('invalid_token')
    if verifier is None and not _looks_like_signed_jwt(token):
        raise ProviderError('invalid_token')
    claims = (verifier or _default_google_verifier)(token)
    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise ProviderError('invalid_issuer')
    if claims.get('aud') not in client_ids:
        raise ProviderError('invalid_audience')
    if not claims.get('sub'):
        raise ProviderError('invalid_token')
    return {
        'subject': str(claims['sub']),
        'email': (claims.get('email') or '').lower(),
        'email_verified': claims.get('email_verified') in (True, 'true'),
        'name': claims.get('name') or '',
    }
