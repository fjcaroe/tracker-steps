"""Offline, explicit-root PKIX/complete-CRL verification for document signers.

OpenSSL performs path validation; this module does not implement PKIX. No OS
trust, AIA/CRL downloads, network, private keys, database or fiscal authority.
Restricted profile: one pinned self-signed root, ordered intermediates, complete
direct CRLs only. Unsupported scope/delta/indirect CRLs fail closed.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import re

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class CertificateTrustError(ValueError):
    """Codes only: never certificate subjects, serials or raw backend errors."""


def require(value, code):
    if not value:
        raise CertificateTrustError('certificate-trust-' + code)


@dataclass(frozen=True)
class RootAnchor:
    certificate_der: bytes = field(repr=False)
    fingerprint_sha256: str


@dataclass(frozen=True)
class CertificateTrustPolicy:
    root: RootAnchor = field(repr=False)
    intermediates_der: tuple = field(repr=False)
    complete_crls_der: tuple = field(repr=False)
    max_crl_age_seconds: int


@dataclass(frozen=True)
class CertificateTrustVerification:
    chain_sha256: tuple
    crls_sha256: tuple
    checked_at: datetime

    def metadata(self):
        return {'certificate_chain_verified': True, 'certificate_revocation_checked': True,
            'certificate_trust_profile': 'explicit-root-ordered-path-complete-direct-crls',
            'certificate_chain_sha256': self.chain_sha256, 'certificate_crls_sha256': self.crls_sha256,
            'certificate_trust_checked_at': self.checked_at.isoformat(),
            'certificate_revocation_scope': 'supplied-complete-crls-at-signing-instant',
            'online_latest_crl_checked': False, 'operating_system_trust_used': False,
            'signer_fiscal_authorization_verified': False, 'fiscal_emission_enabled': False}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _certificate(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 65536, 'certificate-size-or-type')
    try:
        value = x509.load_der_x509_certificate(raw)
        require(value.public_bytes(serialization.Encoding.DER) == raw, 'certificate-trailing-or-noncanonical')
        key = value.public_key()
        require(isinstance(key, rsa.RSAPublicKey) and 2048 <= key.key_size <= 8192, 'rsa-key-profile')
        require(value.signature_hash_algorithm.name in ('sha256', 'sha384', 'sha512'), 'certificate-digest')
        # Loading all extensions detects duplicates/malformed extensions now.
        tuple(value.extensions)
        return value
    except CertificateTrustError:
        raise
    except (ValueError, TypeError, x509.DuplicateExtension, UnsupportedAlgorithm):
        raise CertificateTrustError('certificate-trust-certificate-invalid') from None


def _extension(value, kind):
    try:
        return value.extensions.get_extension_for_class(kind).value
    except x509.ExtensionNotFound:
        raise CertificateTrustError('certificate-trust-required-extension') from None


def verify_signer_trust(certificate_der, fingerprint_sha256, signed_at, policy):
    """Reverify actual DER/path/CRLs at an explicit signing instant, never receipts."""
    require(type(signed_at) is datetime and signed_at.utcoffset() is not None
        and signed_at.microsecond == 0, 'explicit-instant')
    instant = signed_at.astimezone(timezone.utc)
    require(type(policy) is CertificateTrustPolicy and type(policy.root) is RootAnchor, 'explicit-policy')
    require(type(policy.max_crl_age_seconds) is int and 0 < policy.max_crl_age_seconds <= 31 * 86400, 'crl-age-policy')
    require(type(policy.intermediates_der) is tuple and len(policy.intermediates_der) <= 5
        and type(policy.complete_crls_der) is tuple
        and len(policy.complete_crls_der) == len(policy.intermediates_der) + 1, 'complete-path-and-crls')
    for raw, pin in ((certificate_der, fingerprint_sha256),
                     (policy.root.certificate_der, policy.root.fingerprint_sha256)):
        require(type(raw) is bytes and type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin)
            and hmac.compare_digest(_sha(raw), pin), 'pin-mismatch')
    raw_chain = (certificate_der, *policy.intermediates_der, policy.root.certificate_der)
    require(all(type(raw) is bytes and 0 < len(raw) <= 65536 for raw in raw_chain), 'certificate-size-or-type')
    require(len({_sha(raw) for raw in raw_chain}) == len(raw_chain), 'duplicate-path-certificate')
    chain = tuple(_certificate(raw) for raw in raw_chain)
    require(chain[-1].issuer == chain[-1].subject, 'root-must-be-self-issued')
    for index, cert in enumerate(chain):
        require(_utc(cert.not_valid_before) <= instant <= _utc(cert.not_valid_after), 'certificate-time')
        constraints, usage = _extension(cert, x509.BasicConstraints), _extension(cert, x509.KeyUsage)
        require(constraints.ca == (index > 0), 'ca-role')
        require(usage.digital_signature if index == 0 else usage.key_cert_sign and usage.crl_sign, 'key-usage')
        if index + 1 < len(chain):
            issuer = chain[index + 1]
            require(cert.issuer == issuer.subject, 'ordered-issuer')
            require(_extension(cert, x509.AuthorityKeyIdentifier).key_identifier
                == _extension(issuer, x509.SubjectKeyIdentifier).digest, 'authority-key')
    crls = []
    for raw, issuer in zip(policy.complete_crls_der, chain[1:]):
        require(type(raw) is bytes and 0 < len(raw) <= 4 * 1024 * 1024, 'crl-size-or-type')
        try:
            crl = x509.load_der_x509_crl(raw)
            require(crl.public_bytes(serialization.Encoding.DER) == raw, 'crl-trailing-or-noncanonical')
            require(crl.signature_hash_algorithm.name in ('sha256', 'sha384', 'sha512'), 'crl-digest')
            # No scoped, indirect, delta or freshest-CRL semantics are inferred.
            require(all(not ext.critical and isinstance(ext.value, (x509.AuthorityKeyIdentifier, x509.CRLNumber))
                for ext in crl.extensions), 'crl-scope-unsupported')
            require(crl.issuer == issuer.subject
                and _extension(crl, x509.AuthorityKeyIdentifier).key_identifier
                == _extension(issuer, x509.SubjectKeyIdentifier).digest, 'crl-issuer')
            require(crl.next_update is not None and _utc(crl.last_update) <= instant < _utc(crl.next_update)
                and (instant - _utc(crl.last_update)).total_seconds() <= policy.max_crl_age_seconds, 'crl-time-or-age')
            require(len(crl) <= 100000 and crl.is_signature_valid(issuer.public_key()), 'crl-signature')
            serials = set()
            for entry in crl:
                require(entry.serial_number not in serials, 'duplicate-revoked-entry')
                serials.add(entry.serial_number)
                require(all(isinstance(ext.value, (x509.CRLReason, x509.InvalidityDate))
                    for ext in entry.extensions), 'indirect-or-unsupported-entry')
                for ext in entry.extensions:
                    require(not ext.critical and not (isinstance(ext.value, x509.CRLReason)
                        and ext.value.reason == x509.ReasonFlags.remove_from_crl), 'unsupported-entry-reason')
            crls.append(crl)
        except CertificateTrustError:
            raise
        except (ValueError, TypeError, x509.DuplicateExtension, UnsupportedAlgorithm):
            raise CertificateTrustError('certificate-trust-crl-invalid') from None
    try:
        from OpenSSL import crypto
        store = crypto.X509Store()  # Empty store: never load system paths.
        store.set_flags(crypto.X509StoreFlags.X509_STRICT | crypto.X509StoreFlags.CRL_CHECK
            | crypto.X509StoreFlags.CRL_CHECK_ALL | crypto.X509StoreFlags.CHECK_SS_SIGNATURE
            | crypto.X509StoreFlags.POLICY_CHECK)
        store.set_time(instant)
        store.add_cert(crypto.X509.from_cryptography(chain[-1]))
        for crl in crls:
            store.add_crl(crypto.CRL.from_cryptography(crl) if hasattr(crypto, 'CRL') else crl)
        context = crypto.X509StoreContext(store, crypto.X509.from_cryptography(chain[0]),
            [crypto.X509.from_cryptography(cert) for cert in chain[1:-1]])
        verified = context.get_verified_chain()  # Backend performs actual PKIX.
        require(tuple(crypto.dump_certificate(crypto.FILETYPE_ASN1, cert) for cert in verified)
            == raw_chain, 'verified-path-differs')
    except ImportError:
        raise CertificateTrustError('certificate-trust-backend-unavailable') from None
    except (AttributeError, ValueError, TypeError):
        raise CertificateTrustError('certificate-trust-backend-profile-unsupported') from None
    except (crypto.Error, crypto.X509StoreContextError):
        raise CertificateTrustError('certificate-trust-path-or-revocation-invalid') from None
    return CertificateTrustVerification(tuple(_sha(raw) for raw in raw_chain),
        tuple(_sha(raw) for raw in policy.complete_crls_der), instant)
