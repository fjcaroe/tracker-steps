"""Read-only RSA CAF verification, independently implemented from SII's spec.

This is not XMLDSIG, a folio allocator, a DTE emitter, or a trusted-key store.
Callers must supply an independently authenticated authority key and its pin.
Original authorization bytes may contain RSASK: never log or expose them.
"""

import base64
import binascii
from dataclasses import dataclass, field
from datetime import date
import hashlib
import hmac
import re
from typing import Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree


MAX_XML_BYTES = 2 * 1024 * 1024
SII_NAMESPACE = 'http://www.sii.cl/SiiDte'


class CAFError(ValueError):
    """Stable code only: exceptions must not echo XML, names or private keys."""


def _require(condition, code):
    if not condition:
        raise CAFError(code)


def _integer(text, code, allow_zero=False):
    _require(isinstance(text, str) and re.fullmatch(r'[0-9]{1,18}', text), code)
    number = int(text)
    _require(number >= (0 if allow_zero else 1), code)
    return number


def normalize_rut(value):
    """Validate the check digit; presentation separators are caller input only."""
    _require(isinstance(value, str), 'issuer-format')
    value = value.replace('.', '').upper()
    match = re.fullmatch(r'([1-9][0-9]{0,8})-([0-9K])', value)
    _require(match is not None, 'issuer-format')
    body, digit = match.groups()
    total = sum(int(item) * (2 + index % 6)
                for index, item in enumerate(reversed(body)))
    calculated = 11 - total % 11
    _require(digit == ('0' if calculated == 11 else 'K' if calculated == 10
                       else str(calculated)), 'issuer-check-digit')
    return body + '-' + digit


def _b64(value, code):
    _require(isinstance(value, str), code)
    try:
        encoded = re.sub(r'[\t\r\n ]', '', value).encode('ascii')
        result = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError, binascii.Error):
        raise CAFError(code) from None
    _require(bool(result), code)
    return result


def public_key_fingerprint(public_key):
    """SHA256 of DER SubjectPublicKeyInfo, lowercase hexadecimal."""
    _require(isinstance(public_key, rsa.RSAPublicKey), 'authority-key-type')
    der = public_key.public_bytes(serialization.Encoding.DER,
                                  serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


@dataclass(frozen=True)
class TrustAnchor:
    key_id: int
    fingerprint_sha256: str
    public_key_pem: bytes = field(repr=False)

    def key(self):
        _require(type(self.key_id) is int and self.key_id > 0, 'authority-id')
        _require(isinstance(self.fingerprint_sha256, str)
                 and re.fullmatch(r'[0-9a-f]{64}', self.fingerprint_sha256),
                 'authority-fingerprint-format')
        try:
            key = serialization.load_pem_public_key(self.public_key_pem)
        except (TypeError, ValueError):
            raise CAFError('authority-key-format') from None
        actual = public_key_fingerprint(key)
        _require(hmac.compare_digest(actual, self.fingerprint_sha256),
                 'authority-fingerprint-mismatch')
        return key


@dataclass(frozen=True)
class ParsedCAF:
    issuer_rut: str
    document_type: int
    folio_from: int
    folio_to: int
    authorization_date: date
    authority_key_id: int
    document_sha256: str
    has_private_key: bool
    _original: bytes = field(repr=False)
    _caf_original: bytes = field(repr=False)
    _signed_data: bytes = field(repr=False)
    _signature: bytes = field(repr=False)
    _issuer_public_key: object = field(repr=False, compare=False)
    _private_pem: bytes = field(repr=False, default=b'')
    _public_pem: bytes = field(repr=False, default=b'')

    def original_bytes(self):
        """Sensitive original authorization, returned byte for byte; never log."""
        return self._original

    def public_caf_bytes(self):
        """Exact original CAF fragment (no sibling RSASK/RSAPUBK)."""
        return self._caf_original

    def verify_key_pair(self):
        """Check mathematical identity without signing or exposing the secret."""
        _require(self.has_private_key, 'private-key-absent')
        try:
            private = serialization.load_pem_private_key(self._private_pem, password=None)
            public = serialization.load_pem_public_key(self._public_pem)
        except (TypeError, ValueError):
            raise CAFError('authorization-key-format') from None
        _require(isinstance(private, rsa.RSAPrivateKey)
                 and isinstance(public, rsa.RSAPublicKey), 'authorization-key-type')
        expected = self._issuer_public_key.public_numbers()
        _require(private.public_key().public_numbers() == expected
                 and public.public_numbers() == expected, 'authorization-key-mismatch')
        return True


@dataclass(frozen=True)
class VerifiedCAF:
    """Immutable verification receipt, rechecked before folio applicability."""
    caf: ParsedCAF
    authority: TrustAnchor


def _children(element, names):
    _require([etree.QName(child).localname for child in element] == list(names),
             'structure-' + etree.QName(element).localname)
    _require(element.text is None or not element.text.strip(), 'mixed-content')
    for child in element:
        _require(child.tail is None or not child.tail.strip(), 'mixed-content')


def _leaf(element):
    _require(len(element) == 0 and not element.attrib, 'leaf-structure')
    _require(element.text is not None, 'empty-value')
    return element.text


def parse_caf(xml_bytes):
    """Parse a complete authorization or an unwrapped public CAF; no I/O.

    Strict RSA profile. Default SII namespace is accepted; prefixed elements,
    foreign namespaces, comments, PIs, DTDs, duplicate/unknown fields and XML
    extensions are rejected instead of being silently interpreted differently.
    """
    _require(type(xml_bytes) is bytes and 0 < len(xml_bytes) <= MAX_XML_BYTES,
             'xml-size-or-type')
    _require(b'<!' not in xml_bytes, 'xml-declaration-forbidden')
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False,
                             no_network=True, huge_tree=False,
                             remove_comments=False, remove_pis=False)
    try:
        root = etree.fromstring(xml_bytes, parser)
    except (etree.XMLSyntaxError, ValueError):
        raise CAFError('xml-invalid') from None
    _require(root.getprevious() is None and root.getnext() is None,
             'xml-extra-nodes')
    encoding = root.getroottree().docinfo.encoding.upper().replace('_', '-')
    _require(encoding in ('UTF-8', 'ISO-8859-1', 'ISO8859-1', 'ASCII'),
             'xml-encoding')
    try:
        original_text = xml_bytes.decode(encoding)
    except (LookupError, UnicodeError):
        raise CAFError('xml-encoding') from None
    namespace = etree.QName(root).namespace
    _require(namespace in (None, SII_NAMESPACE), 'xml-namespace')
    for element in root.iter():
        _require(isinstance(element.tag, str), 'xml-extra-nodes')
        _require(element.prefix is None and etree.QName(element).namespace == namespace,
                 'xml-namespace')
        _require(set(element.nsmap) <= {None}, 'xml-namespace')
    tag = etree.QName(root).localname
    _require(tag in ('AUTORIZACION', 'CAF'), 'xml-root')
    private = public = b''
    if tag == 'AUTORIZACION':
        _require(not root.attrib, 'authorization-attributes')
        _children(root, ('CAF', 'RSASK', 'RSAPUBK'))
        caf, private_node, public_node = root
        try:
            private = _leaf(private_node).encode('ascii')
            public = _leaf(public_node).encode('ascii')
        except UnicodeError:
            raise CAFError('authorization-key-format') from None
        _require(private.strip() and public.strip(), 'authorization-key-format')
    else:
        caf = root
    _require(dict(caf.attrib) == {'version': '1.0'}, 'caf-version')
    _children(caf, ('DA', 'FRMA'))
    data, signature = caf
    _require(not data.attrib, 'data-attributes')
    _children(data, ('RE', 'RS', 'TD', 'RNG', 'FA', 'RSAPK', 'IDK'))
    issuer, business_name, doc_type, interval, issued_on, rsa_node, key_id = data
    issuer_rut = normalize_rut(_leaf(issuer))
    _require(len(_leaf(business_name)) <= 100 and business_name.text.strip(),
             'issuer-name')
    type_number = _integer(_leaf(doc_type), 'document-type')
    _require(not interval.attrib, 'range-attributes')
    _children(interval, ('D', 'H'))
    start = _integer(_leaf(interval[0]), 'range-start')
    end = _integer(_leaf(interval[1]), 'range-end')
    _require(start <= end, 'range-order')
    authorization_date = _leaf(issued_on)
    _require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', authorization_date),
             'authorization-date')
    try:
        authorization_date = date.fromisoformat(authorization_date)
    except ValueError:
        raise CAFError('authorization-date') from None
    _require(not rsa_node.attrib, 'rsa-attributes')
    _children(rsa_node, ('M', 'E'))
    modulus = int.from_bytes(_b64(_leaf(rsa_node[0]), 'rsa-modulus'), 'big')
    exponent = int.from_bytes(_b64(_leaf(rsa_node[1]), 'rsa-exponent'), 'big')
    # Legacy CAFs use small RSA keys. Do not rewrite/reject historical identity
    # using a newly invented key-size policy; bound parser work to 8192 bits.
    _require(512 <= modulus.bit_length() <= 8192, 'rsa-size')
    try:
        issuer_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
    except (TypeError, ValueError):
        raise CAFError('rsa-invalid') from None
    authority_id = _integer(_leaf(key_id).strip(), 'authority-id')
    _require(dict(signature.attrib) == {'algoritmo': 'SHA1withRSA'}
             and len(signature) == 0, 'signature-algorithm')
    signature_bytes = _b64(signature.text, 'signature-base64')
    # Use lexical terminal content, never etree serialization/c14n: SII's
    # profile preserves entities and inner spaces and uses ISO-8859-1 bytes.
    data_matches = list(re.finditer(r'<DA(?:\s+xmlns\s*=\s*[\"\'][^\"\']*[\"\'])?\s*>.*?</DA\s*>',
                                   original_text, flags=re.DOTALL))
    caf_matches = list(re.finditer(r'<CAF\s[^>]*>.*?</CAF\s*>', original_text,
                                  flags=re.DOTALL))
    _require(len(data_matches) == len(caf_matches) == 1, 'xml-lexical-ambiguity')
    normalized = re.sub(r'\s+xmlns\s*=\s*([\"\'])[^\"\']*\1', '',
                        data_matches[0].group())
    normalized = normalized.replace('\r', '').replace('\n', '')
    normalized = re.sub(r'>[\t ]+<', '><', normalized)
    try:
        signed_data = normalized.encode('iso-8859-1')
        caf_original = caf_matches[0].group().encode(encoding)
    except UnicodeError:
        raise CAFError('data-not-latin1') from None
    return ParsedCAF(issuer_rut, type_number, start, end, authorization_date,
                     authority_id, hashlib.sha256(xml_bytes).hexdigest(),
                     bool(private), xml_bytes, caf_original, signed_data,
                     signature_bytes, issuer_key, private, public)


def verify_caf(caf, authorities: Mapping[int, TrustAnchor]):
    _require(isinstance(caf, ParsedCAF), 'caf-unparsed')
    # Metadata, lexical payload and preserved document must refer to the same
    # authorization even when a caller constructs/replaces a dataclass.
    fresh = parse_caf(caf.original_bytes())
    _require(caf == fresh, 'caf-receipt-mismatch')
    caf = fresh
    anchor = authorities.get(caf.authority_key_id)
    _require(isinstance(anchor, TrustAnchor)
             and anchor.key_id == caf.authority_key_id, 'authority-untrusted')
    try:
        anchor.key().verify(caf._signature, caf._signed_data,
                            padding.PKCS1v15(), hashes.SHA1())
    except InvalidSignature:
        raise CAFError('signature-invalid') from None
    if caf.has_private_key:
        caf.verify_key_pair()
    return VerifiedCAF(caf, anchor)


def validate_folio(verified, *, issuer_rut, document_type, folio, emission_date=None):
    """Check one explicit folio, never select/increment/reserve a counter.

    Optional date rejects emission before authorization. It makes no assertion
    about revocation, exhaustion, CAF expiry or SII acceptance (external state).
    """
    _require(isinstance(verified, VerifiedCAF), 'caf-unverified')
    # Reverify the receipt, including the pinned key, so forged/mutated data
    # objects are never an alternate path around signature validation.
    verify_caf(verified.caf, {verified.authority.key_id: verified.authority})
    caf = verified.caf
    _require(normalize_rut(issuer_rut) == caf.issuer_rut, 'issuer-mismatch')
    _require(type(document_type) is int and document_type == caf.document_type,
             'document-type-mismatch')
    _require(type(folio) is int and caf.folio_from <= folio <= caf.folio_to,
             'folio-outside-range')
    if emission_date is not None:
        _require(type(emission_date) is date, 'emission-date-format')
        _require(emission_date >= caf.authorization_date, 'emission-before-authorization')
    return caf


def select_caf(candidates: Sequence[VerifiedCAF], **folio_context):
    """Require exactly one trusted CAF for an already chosen folio; no writes."""
    eligible = []
    for candidate in candidates:
        try:
            eligible.append(validate_folio(candidate, **folio_context))
        except CAFError as error:
            if str(error) not in ('issuer-mismatch', 'document-type-mismatch',
                                  'folio-outside-range', 'emission-before-authorization'):
                raise
    _require(len(eligible) == 1, 'folio-no-caf' if not eligible else 'folio-ambiguous')
    return eligible[0]
