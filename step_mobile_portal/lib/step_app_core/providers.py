"""Validación en servidor de identidades externas. Nunca se confía en lo que dice el cliente."""


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


def verify_google_id_token(token, client_ids, verifier=None) -> dict:
    """Devuelve {'subject', 'email', 'email_verified', 'name'} o lanza ProviderError."""
    client_ids = [c for c in (client_ids or []) if c]
    if not client_ids:
        raise ProviderError('provider_not_configured')
    if not isinstance(token, str) or not token:
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
