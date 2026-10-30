"""Offline TED/FRMT verification, independently implemented from SII Annex2.

No signing, PDF417, XMLDSIG, network, folio allocation or fiscal state changes.
Original TED/CAF bytes remain opaque and unchanged. A signature matching a CAF
key does not authenticate its authority: only verify_ted checks a pinned anchor.
See TED.md for primary sources, exact admitted profile and remaining gates.
"""
from dataclasses import dataclass, field
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
import hashlib
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from .caf import CAFError, MAX_XML_BYTES, SII_NAMESPACE, _b64, _children, normalize_rut, parse_caf, verify_caf


ORDINARY_TYPES = frozenset((33, 34, 46, 52, 56, 61))
EXPORT_TYPES = frozenset((110, 111, 112))


class TEDError(CAFError):
    """Stable codes only; never include payloads, names, amounts or secrets."""


def _require(condition, code):
    if not condition:
        raise TEDError(code)


def _text(node, *, empty=False):
    _require(len(node) == 0 and not node.attrib, 'ted-leaf-structure')
    value = node.text or ''
    _require(empty or bool(value), 'ted-empty-value')
    _require(not any(ord(char) < 32 or ord(char) == 127 for char in value), 'ted-control-character')
    try:
        value.encode('latin1')
    except UnicodeError:
        raise TEDError('ted-text-not-latin1') from None
    return value


def _integer(value, *, maximum, code, minimum=0):
    _require(re.fullmatch(r'[0-9]{1,24}', value) is not None, code)
    result = int(value)
    _require(minimum <= result <= maximum, code)
    return result


def _rut(value):
    try:
        normalized = normalize_rut(value)
    except CAFError:
        raise TEDError('ted-rut-invalid') from None
    _require(value == normalized, 'ted-rut-format')
    return normalized


def _date(value):
    _require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value), 'ted-date-format')
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise TEDError('ted-date-invalid') from None
    _require(date(2000, 1, 1) <= result <= date(2050, 12, 31), 'ted-date-range')
    return result


def _amount(value, document_type):
    # The three official DTE families have different MNT contracts. Decimal
    # parsing is exact; no float, currency conversion, rounding or quantization.
    if document_type in ORDINARY_TYPES:
        return Decimal(_integer(value, maximum=2**64 - 1, code='ted-amount-unsigned'))
    if document_type == 43:
        _require(re.fullmatch(r'-?[0-9]{1,24}', value), 'ted-amount-liquidation')
        result = int(value)
        _require(abs(result) <= 10**18 - 1, 'ted-amount-liquidation')
        return Decimal(result)
    _require(document_type in EXPORT_TYPES, 'ted-document-type-unsupported')
    _require(re.fullmatch(r'[0-9]{1,24}(?:\.[0-9]{1,4})?', value), 'ted-amount-export')
    result = Decimal(value)
    _require(Decimal('0') <= result <= Decimal('99999999999999.9999'), 'ted-amount-export')
    return result


@dataclass(frozen=True, repr=False)
class ParsedTED:
    issuer_rut: str
    document_type: int
    folio: int
    emission_date: date
    receiver_rut: str
    receiver_name: str
    total: Decimal
    total_text: str
    first_item: str
    stamp_datetime: datetime
    document_sha256: str
    _original: bytes = field(repr=False)
    _caf_fragment: bytes = field(repr=False)
    _signed_data: bytes = field(repr=False)
    _signature: bytes = field(repr=False)
    _caf: object = field(repr=False)

    def __repr__(self):
        return 'ParsedTED(document_sha256=%r)' % self.document_sha256

    def original_bytes(self):
        return self._original

    def public_caf_bytes(self):
        return self._caf_fragment


@dataclass(frozen=True)
class TEDContext:
    """Expected TED values supplied by a separately authorized DTE consumer."""
    issuer_rut: str = field(repr=False)
    document_type: int
    folio: int
    emission_date: date
    receiver_rut: str = field(repr=False)
    receiver_name: str = field(repr=False)
    total: Decimal = field(repr=False)
    first_item: str = field(repr=False)


@dataclass(frozen=True)
class TEDVerification:
    ted: ParsedTED = field(repr=False)
    caf_authority_verified: bool
    expected_context_matched: bool

    def metadata(self):
        ted = self.ted
        return {'ted_sha256': ted.document_sha256,
            'caf_fragment_sha256': hashlib.sha256(ted.public_caf_bytes()).hexdigest(),
            'issuer_rut': ted.issuer_rut, 'document_type': ted.document_type,
            'folio': ted.folio, 'emission_date': ted.emission_date.isoformat(),
            'total_text': ted.total_text, 'stamp_datetime': ted.stamp_datetime.isoformat(),
            'ted_signature_verified': True, 'caf_authority_verified': self.caf_authority_verified,
            'expected_context_matched': self.expected_context_matched,
            'folio_operations_enabled': False, 'sii_acceptance_certified': False,
            'dte_xml_signature_verified': False}


def parse_ted(xml_bytes):
    """Parse one unwrapped RSA TED; hostile/ambiguous XML fails closed."""
    _require(type(xml_bytes) is bytes and 0 < len(xml_bytes) <= MAX_XML_BYTES, 'ted-size-or-type')
    _require(b'<!' not in xml_bytes and b'\x00' not in xml_bytes, 'ted-declaration-forbidden')
    try:
        root = etree.fromstring(xml_bytes, parser=etree.XMLParser(resolve_entities=False,
            load_dtd=False, no_network=True, huge_tree=False, remove_comments=False, remove_pis=False))
    except (etree.XMLSyntaxError, ValueError):
        raise TEDError('ted-xml-invalid') from None
    _require(root.getprevious() is None and root.getnext() is None, 'ted-extra-nodes')
    encoding = root.getroottree().docinfo.encoding.upper().replace('_', '-')
    _require(encoding in ('UTF-8', 'ISO-8859-1', 'ISO8859-1', 'ASCII'), 'ted-encoding')
    namespace = etree.QName(root).namespace
    _require(namespace in (None, SII_NAMESPACE), 'ted-namespace')
    for node in root.iter():
        _require(isinstance(node.tag, str) and node.prefix is None
            and etree.QName(node).namespace == namespace and set(node.nsmap) <= {None}, 'ted-namespace')
    _require(etree.QName(root).localname == 'TED' and dict(root.attrib) == {'version': '1.0'}, 'ted-root-or-version')
    try:
        _children(root, ('DD', 'FRMT'))
        data, signature = root
        _require(not data.attrib, 'ted-data-attributes')
        _children(data, ('RE', 'TD', 'F', 'FE', 'RR', 'RSR', 'MNT', 'IT1', 'CAF', 'TSTED'))
    except TEDError:
        raise
    except CAFError as error:
        raise TEDError('ted-' + str(error)) from None
    issuer, kind, folio, emitted, receiver, name, amount, item, caf_node, timestamp = data
    issuer_rut, receiver_rut = _rut(_text(issuer)), _rut(_text(receiver))
    document_type = _integer(_text(kind), maximum=999, code='ted-document-type', minimum=1)
    _require(document_type in ORDINARY_TYPES | EXPORT_TYPES | {43}, 'ted-document-type-unsupported')
    folio_number = _integer(_text(folio), maximum=10**10 - 1, code='ted-folio', minimum=1)
    emission_date = _date(_text(emitted))
    receiver_name, first_item = _text(name, empty=True), _text(item, empty=True)
    _require(len(receiver_name) <= 40 and len(first_item) <= 40, 'ted-description-length')
    amount_text = _text(amount)
    total = _amount(amount_text, document_type)
    stamp_text = _text(timestamp)
    _require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}', stamp_text), 'ted-timestamp-format')
    try:
        stamp = datetime.fromisoformat(stamp_text)
    except ValueError:
        raise TEDError('ted-timestamp-invalid') from None
    _date(stamp_text[:10])
    _require(dict(signature.attrib) == {'algoritmo': 'SHA1withRSA'} and len(signature) == 0, 'ted-signature-algorithm')
    try:
        signature_bytes = _b64(signature.text, 'ted-signature-base64')
        text = xml_bytes.decode(encoding)
    except CAFError as error:
        raise TEDError(str(error)) from None
    except UnicodeError:
        raise TEDError('ted-encoding') from None
    dd = list(re.finditer(r'<DD(?:\s+xmlns\s*=\s*[\"\'][^\"\']*[\"\'])?\s*>.*?</DD\s*>', text, re.S))
    fragments = list(re.finditer(r'<CAF\s[^>]*>.*?</CAF\s*>', text, re.S))
    _require(len(dd) == len(fragments) == 1, 'ted-lexical-ambiguity')
    normalized = re.sub(r'\s+xmlns\s*=\s*([\"\'])[^\"\']*\1', '', dd[0].group())
    normalized = normalized.replace('\r', '').replace('\n', '')
    normalized = re.sub(r'>[\t ]+<', '><', normalized)
    try:
        signed_data = normalized.encode('latin1')
        fragment = fragments[0].group().encode(encoding)
        # Decoder scaffolding only, never persisted or returned as an original.
        # The exact embedded fragment and complete TED are retained separately.
        parsed_caf = parse_caf(('<?xml version="1.0" encoding="' + encoding + '"?>\n').encode('ascii') + fragment)
    except UnicodeError:
        raise TEDError('ted-text-not-latin1') from None
    except CAFError as error:
        raise TEDError('ted-caf-' + str(error)) from None
    _require(parsed_caf.issuer_rut == issuer_rut and parsed_caf.document_type == document_type, 'ted-caf-identity-mismatch')
    _require(parsed_caf.folio_from <= folio_number <= parsed_caf.folio_to, 'ted-folio-outside-caf')
    _require(emission_date >= parsed_caf.authorization_date, 'ted-before-caf-authorization')
    return ParsedTED(issuer_rut, document_type, folio_number, emission_date, receiver_rut,
        receiver_name, total, amount_text, first_item, stamp, hashlib.sha256(xml_bytes).hexdigest(),
        xml_bytes, fragment, signed_data, signature_bytes, parsed_caf)


def _verify_signature(ted):
    key = ted._caf._issuer_public_key
    _require(len(ted._signature) == (key.key_size + 7) // 8, 'ted-signature-size')
    try:
        key.verify(ted._signature, ted._signed_data, padding.PKCS1v15(), hashes.SHA1())
    except InvalidSignature:
        raise TEDError('ted-signature-invalid') from None


def _match_context(ted, expected):
    if expected is None:
        return False
    _require(isinstance(expected, TEDContext), 'ted-context-type')
    _require(type(expected.document_type) is int and type(expected.folio) is int
        and type(expected.emission_date) is date and type(expected.total) in (Decimal, int), 'ted-context-values')
    _require(all(type(value) is str for value in (expected.issuer_rut, expected.receiver_rut,
        expected.receiver_name, expected.first_item)), 'ted-context-values')
    _require(type(expected.total) is int or expected.total.is_finite(), 'ted-context-values')
    _require((ted.issuer_rut, ted.document_type, ted.folio, ted.emission_date,
        ted.receiver_rut, ted.receiver_name, ted.total, ted.first_item) ==
        (expected.issuer_rut, expected.document_type, expected.folio, expected.emission_date,
         expected.receiver_rut, expected.receiver_name, expected.total, expected.first_item), 'ted-context-mismatch')
    return True


def check_ted_against_caf(xml_bytes, original_caf_bytes, *, expected=None):
    """Check FRMT against the exact stored CAF; deliberately no authority claim."""
    ted = parse_ted(xml_bytes)
    try:
        stored = parse_caf(original_caf_bytes)
    except CAFError as error:
        raise TEDError('stored-caf-' + str(error)) from None
    _require(ted.public_caf_bytes() == stored.public_caf_bytes(), 'ted-stored-caf-mismatch')
    _verify_signature(ted)
    return TEDVerification(ted, False, _match_context(ted, expected))


def verify_ted(xml_bytes, authorities, *, expected=None):
    """Reparse and verify CAF FRMA through an externally authenticated key pin."""
    _require(isinstance(authorities, Mapping), 'ted-authority-map')
    ted = parse_ted(xml_bytes)
    try:
        verify_caf(ted._caf, authorities)
    except CAFError as error:
        raise TEDError('ted-caf-' + str(error)) from None
    _verify_signature(ted)
    return TEDVerification(ted, True, _match_context(ted, expected))
