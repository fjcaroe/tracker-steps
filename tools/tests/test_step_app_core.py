from datetime import datetime, timedelta

import pytest

from step_app_core import authz, passwords, providers, sessions, tokens

NOW = datetime(2026, 10, 4, 12, 0)
H = timedelta(hours=1)
ROLES = {('colaciones', 'operador'): ['colaciones.register'], ('colaciones', 'persona'): ['colaciones.read_own'],
         ('mobilization', 'conductor'): ['mobilization.drive']}


def membership(**kw):
    return {'id': 1, 'state': 'active', 'valid_from': None, 'valid_to': None, **kw}


def grant(**kw):
    return {'membership_id': 1, 'module': 'colaciones', 'role': 'operador', 'valid_from': None, 'valid_to': None,
            'revoked_at': None, **kw}


def test_tokens_solo_se_comparan_por_huella():
    t = tokens.new_token()
    assert len(t) >= 43 and tokens.new_token() != t
    assert tokens.verify_token(t, tokens.hash_token(t))
    assert not tokens.verify_token(t + 'x', tokens.hash_token(t))
    assert not tokens.verify_token('', tokens.hash_token(t)) and not tokens.verify_token(t, None)


def test_contrasenas():
    stored = passwords.hash_password('una-clave-larga-123')
    assert stored.startswith('scrypt$') and 'una-clave' not in stored
    assert passwords.verify_password('una-clave-larga-123', stored)
    assert not passwords.verify_password('otra-clave-larga-123', stored)
    assert not passwords.verify_password('x', None)
    assert passwords.hash_password('una-clave-larga-123') != stored  # sal distinta
    assert passwords.password_problem('corta') == 'too_short'
    assert passwords.password_problem('Ana@Mail.cl', 'ana@mail.cl') == 'same_as_email'
    assert passwords.password_problem('aaaaaaaaaaaa') == 'too_simple'
    assert passwords.password_problem('clave-segura-2026') is None


def test_correos():
    assert passwords.normalize_email('  Ana@Mail.CL ') == 'ana@mail.cl'
    assert passwords.valid_email('ana@mail.cl') and not passwords.valid_email('ana@') and not passwords.valid_email('a b@c.cl')


def test_membresia_suspendida_no_da_permisos():
    g = [grant()]
    assert authz.effective_permissions(membership(), g, ROLES, NOW) == {'colaciones.register'}
    assert authz.effective_permissions(membership(state='suspended'), g, ROLES, NOW) == set()
    assert authz.effective_permissions(membership(state='invited'), g, ROLES, NOW) == set()
    assert authz.effective_permissions(membership(valid_to=NOW - H), g, ROLES, NOW) == set()


def test_vigencia_y_revocacion_de_concesion():
    assert authz.grant_active_at(grant(valid_from=NOW - H, valid_to=NOW + H), NOW)
    assert not authz.grant_active_at(grant(valid_from=NOW + H), NOW)
    assert not authz.grant_active_at(grant(valid_to=NOW), NOW)  # el fin es exclusivo
    assert not authz.grant_active_at(grant(revoked_at=NOW), NOW)
    assert authz.grant_active_at(grant(revoked_at=NOW + H), NOW)


def test_concesion_de_otra_membresia_no_cuenta():
    other = grant(membership_id=2)
    assert authz.effective_permissions(membership(), [other], ROLES, NOW) == set()
    assert authz.enabled_modules(membership(), [other], {'colaciones'}, NOW) == []


def test_modulos_habilitados_requieren_estar_instalados():
    g = [grant(), grant(module='mobilization', role='conductor'), grant(role='persona')]
    assert authz.enabled_modules(membership(), g, {'colaciones'}, NOW) == ['colaciones']
    assert authz.enabled_modules(membership(), g, {'colaciones', 'mobilization'}, NOW) == ['colaciones', 'mobilization']


def test_alcance_de_concesion():
    assert authz.scope_allows(grant(), 7)
    assert authz.scope_allows(grant(scope_ids=[7, 8]), 7)
    assert not authz.scope_allows(grant(scope_ids=[7, 8]), 9)


def test_autorizacion_offline_vence():
    until = authz.offline_until(NOW, 72)
    assert until == NOW + timedelta(hours=72)
    assert authz.offline_allowed(NOW + timedelta(hours=71), until)
    assert not authz.offline_allowed(NOW + timedelta(hours=72), until)
    assert not authz.offline_allowed(NOW, None)


def test_evento_capturado_antes_de_la_revocacion_se_acepta():
    g = [grant(valid_from=NOW - 10 * H, revoked_at=NOW)]
    assert authz.event_acceptable(NOW - H, g, 'colaciones', 'operador') == (True, 'ok')
    assert authz.event_acceptable(NOW + H, g, 'colaciones', 'operador') == (False, 'grant_not_valid_at_capture')
    assert authz.event_acceptable(NOW - 20 * H, g, 'colaciones', 'operador') == (False, 'grant_not_valid_at_capture')
    assert authz.event_acceptable(NOW, g, 'colaciones', 'persona') == (False, 'no_grant')


def test_evento_capturado_despues_del_fin_de_acceso_se_rechaza():
    g = [grant(valid_from=NOW - 10 * H)]  # la concesión no se revocó, pero la membresía se suspendió en NOW
    assert authz.event_acceptable(NOW - H, g, 'colaciones', 'operador', access_ended_at=NOW) == (True, 'ok')
    assert authz.event_acceptable(NOW, g, 'colaciones', 'operador', access_ended_at=NOW) == (False, 'access_ended_before_capture')
    assert authz.event_acceptable(NOW + H, g, 'colaciones', 'operador', access_ended_at=NOW) == (False, 'access_ended_before_capture')


def test_evento_fuera_del_alcance_de_la_concesion_se_rechaza():
    g = [grant(scope_ids=[7])]
    assert authz.event_acceptable(NOW, g, 'colaciones', 'operador', resource_id=7) == (True, 'ok')
    assert authz.event_acceptable(NOW, g, 'colaciones', 'operador', resource_id=9) == (False, 'resource_out_of_scope')
    assert authz.event_acceptable(NOW, [grant()], 'colaciones', 'operador', resource_id=9) == (True, 'ok')


def test_sesion_emite_pares_distintos_y_guarda_huellas():
    a, b = sessions.issue(NOW), sessions.issue(NOW)
    assert a['access'] != b['access'] and a['refresh'] != b['refresh']
    assert a['access'] not in (a['access_hash'], a['refresh_hash'])
    record = {'access_hash': a['access_hash'], 'access_expires_at': a['access_expires_at'], 'revoked_at': None}
    assert sessions.classify_access(record, a['access'], NOW) == sessions.OK
    assert sessions.classify_access(record, a['access'], NOW + timedelta(minutes=31)) == sessions.EXPIRED
    assert sessions.classify_access(record, b['access'], NOW) == sessions.UNKNOWN
    assert sessions.classify_access({**record, 'revoked_at': NOW}, a['access'], NOW) == sessions.REVOKED
    assert sessions.classify_access(None, a['access'], NOW) == sessions.UNKNOWN


def test_renovacion_rotatoria_detecta_reutilizacion():
    first = sessions.issue(NOW)
    second = sessions.issue(NOW)
    # Tras rotar, la sesión guarda el refresh nuevo y recuerda el anterior.
    record = {'refresh_hash': second['refresh_hash'], 'previous_refresh_hash': first['refresh_hash'],
              'refresh_expires_at': second['refresh_expires_at'], 'revoked_at': None}
    assert sessions.classify_refresh(record, second['refresh'], NOW) == sessions.OK
    assert sessions.classify_refresh(record, first['refresh'], NOW) == sessions.REUSED
    assert sessions.classify_refresh(record, 'inventado', NOW) == sessions.UNKNOWN
    assert sessions.classify_refresh(record, second['refresh'], NOW + timedelta(days=31)) == sessions.EXPIRED
    assert sessions.classify_refresh({**record, 'revoked_at': NOW}, second['refresh'], NOW) == sessions.REVOKED


GOOD = {'iss': 'https://accounts.google.com', 'aud': 'cliente-1', 'sub': '1234', 'email': 'Ana@Mail.cl',
        'email_verified': True, 'name': 'Ana'}


def test_google_acepta_token_valido_e_identifica_por_sub():
    out = providers.verify_google_id_token('tok', ['cliente-1'], verifier=lambda t: GOOD)
    assert out == {'subject': '1234', 'email': 'ana@mail.cl', 'email_verified': True, 'name': 'Ana'}


@pytest.mark.parametrize('claims,code', [
    ({**GOOD, 'iss': 'https://evil.example'}, 'invalid_issuer'),
    ({**GOOD, 'aud': 'otro-cliente'}, 'invalid_audience'),
    ({**GOOD, 'sub': ''}, 'invalid_token'),
])
def test_google_rechaza_emisor_audiencia_y_sub_invalidos(claims, code):
    with pytest.raises(providers.ProviderError) as e:
        providers.verify_google_id_token('tok', ['cliente-1'], verifier=lambda t: claims)
    assert e.value.code == code


def test_google_sin_configuracion_no_autentica():
    with pytest.raises(providers.ProviderError) as e:
        providers.verify_google_id_token('tok', [], verifier=lambda t: GOOD)
    assert e.value.code == 'provider_not_configured'


def test_google_propaga_token_expirado_de_la_biblioteca():
    def boom(_):
        raise providers.ProviderError('invalid_token')
    with pytest.raises(providers.ProviderError) as e:
        providers.verify_google_id_token('tok', ['cliente-1'], verifier=boom)
    assert e.value.code == 'invalid_token'
