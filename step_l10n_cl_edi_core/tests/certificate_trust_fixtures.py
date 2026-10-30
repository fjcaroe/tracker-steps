"""Ephemeral PKIX/CRL fixtures, never operational authorities or credentials."""
from datetime import datetime, timezone, timedelta
import hashlib

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ObjectIdentifier

from ..certificate_trust import RootAnchor, CertificateTrustPolicy
from ..dte_signature import CertificatePin


NOW = datetime(2026, 10, 1, 12, 3, 1, tzinfo=timezone.utc)


def der(value):
    return value.public_bytes(serialization.Encoding.DER)


def certificate(key, issuer_key, subject, issuer, serial, *, ca, path_length=None, extra=None):
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key()).serial_number(serial)
        .not_valid_before(NOW - timedelta(days=30)).not_valid_after(NOW + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca, path_length), critical=True)
        .add_extension(x509.KeyUsage(not ca, False, False, False, False, ca, ca, None, None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False))
    if extra:
        builder = builder.add_extension(*extra)
    return builder.sign(issuer_key, hashes.SHA256())


def crl(key, name, *, revoked=(), age=3600, future=3600, extra=None, wrong_key=None):
    builder = (x509.CertificateRevocationListBuilder().issuer_name(name)
        .last_update(NOW - timedelta(seconds=age)).next_update(NOW + timedelta(seconds=future))
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .add_extension(x509.CRLNumber(1), critical=False))
    for serial in revoked:
        builder = builder.add_revoked_certificate(x509.RevokedCertificateBuilder()
            .serial_number(serial).revocation_date(NOW - timedelta(seconds=7200)).build())
    if extra:
        builder = builder.add_extension(*extra)
    return der(builder.sign(wrong_key or key, hashes.SHA256()))


def chain_fixture(leaf_key, *, root_path_length=1, leaf_extra=None, revoked_leaf=False,
                  revoked_intermediate=False, crl_extra=None, root_crl_extra=None, age=3600, future=3600):
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    middle_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    def name(text):
        return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SYNTHETIC ONLY ' + text),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, '11111111-1')])
    root_name, middle_name, leaf_name = name('ROOT'), name('CA'), name('LEAF')
    root = certificate(root_key, root_key, root_name, root_name, 1, ca=True, path_length=root_path_length)
    middle = certificate(middle_key, root_key, middle_name, root_name, 2, ca=True, path_length=0)
    leaf = certificate(leaf_key, middle_key, leaf_name, middle_name, 3, ca=False, extra=leaf_extra)
    pin = CertificatePin(der(leaf), hashlib.sha256(der(leaf)).hexdigest())
    policy = CertificateTrustPolicy(RootAnchor(der(root), hashlib.sha256(der(root)).hexdigest()),
        (der(middle),), (crl(middle_key, middle_name, revoked=(3,) if revoked_leaf else (),
            extra=crl_extra, age=age, future=future), crl(root_key, root_name,
            revoked=(2,) if revoked_intermediate else (), extra=root_crl_extra)), 86400)
    return pin, policy


UNKNOWN_CRITICAL = (x509.UnrecognizedExtension(ObjectIdentifier('1.2.3.4.5.6.7'), b'opaque'), True)
