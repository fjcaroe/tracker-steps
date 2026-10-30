"""SII-profile XMLDSig construction/verification, entirely offline.

Explicit new unsigned DTE, CAF, context, private-key object and certificate pin
are inputs. No key loading from services, credentials, implicit company policy,
network, model writes, folios or fiscal authorization. Verification retains raw
bytes; construction appends only a new Signature without serializing the DTE.
"""
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import re
import textwrap

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from . import ted
from .caf import CAFError, MAX_XML_BYTES, SII_NAMESPACE, _b64
from .dte_schema import SchemaError, validate_dte_schema


DS = 'http://www.w3.org/2000/09/xmldsig#'
C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
RSA_SHA1 = DS + 'rsa-sha1'
SHA1 = DS + 'sha1'
DOCUMENT_TAGS = {'Documento': ted.ORDINARY_TYPES, 'Liquidacion': {43}, 'Exportaciones': ted.EXPORT_TYPES}


class DTEError(ValueError):
    """Stable codes only, never certificate contents, payload or private keys."""


def _require(condition, code):
    if not condition:
        raise DTEError(code)


@dataclass(frozen=True)
class CertificatePin:
    certificate_der: bytes = field(repr=False)
    fingerprint_sha256: str


@dataclass(frozen=True)
class DTEContext:
    document_id: str
    ted_context: ted.TEDContext = field(repr=False)
    signed_at: datetime


@dataclass(frozen=True)
class DTEVerification:
    _original: bytes = field(repr=False)
    document_id: str
    certificate_sha256: str
    caf_authority_verified: bool
    ted_verification: ted.TEDVerification = field(repr=False)
    signed_at: datetime

    def original_bytes(self):
        return self._original

    def metadata(self):
        return dict(self.ted_verification.metadata(), dte_sha256=hashlib.sha256(self._original).hexdigest(),
            document_id=self.document_id, certificate_sha256=self.certificate_sha256,
            dte_xml_signature_verified=True, sii_schema_verified=True,
            certificate_pin_matched=True, certificate_time_checked=True,
            caf_authority_verified=self.caf_authority_verified, signed_at=self.signed_at.isoformat(),
            certificate_chain_verified=False, certificate_revocation_checked=False,
            signer_fiscal_authorization_verified=False, tax_calculation_certified=False,
            business_record_identity_adopted=False, fiscal_emission_enabled=False,
            sii_acceptance_certified=False, folio_operations_enabled=False)


def _context(context):
    _require(isinstance(context, DTEContext) and isinstance(context.ted_context, ted.TEDContext), 'dte-context-required')
    _require(type(context.document_id) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,79}', context.document_id), 'dte-document-id')
    _require(type(context.signed_at) is datetime and context.signed_at.utcoffset() is not None
        and context.signed_at.microsecond == 0, 'dte-explicit-signature-instant-required')


def _parse(raw, *, signed):
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_XML_BYTES, 'dte-size-or-type')
    _require(b'<!' not in raw and b'\x00' not in raw, 'dte-declaration-forbidden')
    try:
        root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, load_dtd=False,
            no_network=True, huge_tree=False, remove_comments=False, remove_pis=False))
    except (ValueError, etree.XMLSyntaxError):
        raise DTEError('dte-xml-invalid') from None
    _require(root.getprevious() is None and root.getnext() is None, 'dte-extra-nodes')
    _require(root.tag == '{%s}DTE' % SII_NAMESPACE and root.prefix is None
        and root.nsmap == {None: SII_NAMESPACE} and dict(root.attrib) == {'version': '1.0'}, 'dte-root-profile')
    encoding = root.getroottree().docinfo.encoding.upper().replace('_', '-')
    _require(encoding in ('UTF-8', 'ISO-8859-1', 'ISO8859-1', 'ASCII'), 'dte-encoding')
    _require(len(root) == (2 if signed else 1), 'dte-single-document-and-signature-required')
    document = root[0]
    _require(isinstance(document.tag, str) and etree.QName(document).namespace == SII_NAMESPACE
        and etree.QName(document).localname in DOCUMENT_TAGS
        and set(document.attrib) == {'ID'}, 'dte-document-node')
    if signed:
        _require(root[1].tag == '{%s}Signature' % DS, 'dte-signature-position')
    for node in root.iter():
        _require(isinstance(node.tag, str) and etree.QName(node).namespace in (SII_NAMESPACE, DS), 'dte-namespace')
        _require(set(node.nsmap.values()) <= {SII_NAMESPACE, DS}, 'dte-extra-namespace')
        if etree.QName(node).namespace == SII_NAMESPACE:
            _require(node.prefix is None, 'dte-prefixed-data-unsupported')
        for key in node.attrib:
            if etree.QName(key).localname.lower() == 'id':
                _require(node is document and key == 'ID', 'dte-duplicate-or-alternate-id')
        for value in (node.text, node.tail):
            if value:
                try:
                    value.encode('latin1')
                except UnicodeError:
                    raise DTEError('dte-text-not-latin1') from None
    _require(sum(node.tag == '{%s}Signature' % DS for node in root.iter()) == int(signed), 'dte-nested-or-duplicate-signature')
    return root, document, encoding


def _leaf(document, path):
    nodes = document.findall('/'.join('{%s}%s' % (SII_NAMESPACE, name) for name in path.split('/')))
    _require(len(nodes) == 1 and len(nodes[0]) == 0 and not nodes[0].attrib
        and nodes[0].text is not None, 'dte-required-context-leaf')
    return nodes[0].text


def _bound_ted(raw, document, encoding, original_caf, context, authorities):
    _context(context)
    _require(document.get('ID') == context.document_id, 'dte-context-document-id-mismatch')
    try:
        kind = ted._integer(_leaf(document, 'Encabezado/IdDoc/TipoDTE'), maximum=999, code='dte-kind', minimum=1)
        _require(kind in DOCUMENT_TAGS[etree.QName(document).localname], 'dte-kind-family-mismatch')
        folio = ted._integer(_leaf(document, 'Encabezado/IdDoc/Folio'), maximum=10**10 - 1, code='dte-folio', minimum=1)
        emitted = ted._date(_leaf(document, 'Encabezado/IdDoc/FchEmis'))
        amount = ted._amount(_leaf(document, 'Encabezado/Totales/MntTotal'), kind)
        details = document.findall('{%s}Detalle' % SII_NAMESPACE)
        _require(bool(details), 'dte-first-detail-required')
        actual = ted.TEDContext(_leaf(document, 'Encabezado/Emisor/RUTEmisor'), kind, folio, emitted,
            _leaf(document, 'Encabezado/Receptor/RUTRecep'),
            _leaf(document, 'Encabezado/Receptor/RznSocRecep')[:40], amount, _leaf(details[0], 'NmbItem')[:40])
        matches = list(re.finditer(br'<TED\s[^>]*>.*?</TED\s*>', raw, re.S))
        _require(len(matches) == 1 and len(document.findall('{%s}TED' % SII_NAMESPACE)) == 1, 'dte-single-lexical-ted-required')
        framed = ('<?xml version="1.0" encoding="' + encoding + '"?>\n').encode('ascii') + matches[0].group()
        checked = ted.check_ted_against_caf(framed, original_caf, expected=actual)
        ted._match_context(checked.ted, context.ted_context)
        if authorities is not None:
            checked = ted.verify_ted(framed, authorities, expected=context.ted_context)
    except CAFError as error:
        raise DTEError('dte-' + str(error)) from None
    local = context.signed_at.replace(tzinfo=None).isoformat(timespec='seconds')
    _require(_leaf(document, 'TmstFirma') == local, 'dte-signature-time-context-mismatch')
    _require(checked.ted.emission_date <= context.signed_at.date()
        and checked.ted.stamp_datetime <= context.signed_at.replace(tzinfo=None), 'dte-signature-before-document-or-ted')
    return checked


def _certificate(pin, context):
    _context(context)
    _require(isinstance(pin, CertificatePin) and type(pin.certificate_der) is bytes
        and 0 < len(pin.certificate_der) <= 64 * 1024 and type(pin.fingerprint_sha256) is str
        and re.fullmatch(r'[0-9a-f]{64}', pin.fingerprint_sha256), 'dte-certificate-pin-required')
    _require(hmac.compare_digest(hashlib.sha256(pin.certificate_der).hexdigest(), pin.fingerprint_sha256), 'dte-certificate-pin-mismatch')
    try:
        certificate = x509.load_der_x509_certificate(pin.certificate_der)
    except (TypeError, ValueError):
        raise DTEError('dte-certificate-invalid') from None
    _require(certificate.public_bytes(serialization.Encoding.DER) == pin.certificate_der,
        'dte-certificate-noncanonical-or-trailing-data')
    key = certificate.public_key()
    _require(isinstance(key, rsa.RSAPublicKey) and 512 <= key.key_size <= 8192, 'dte-certificate-rsa-required')
    before = certificate.not_valid_before_utc if hasattr(certificate, 'not_valid_before_utc') else certificate.not_valid_before.replace(tzinfo=timezone.utc)
    after = certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after.replace(tzinfo=timezone.utc)
    _require(before <= context.signed_at.astimezone(timezone.utc) <= after, 'dte-certificate-time-invalid')
    try:
        usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        _require(usage.digital_signature, 'dte-certificate-signature-usage-denied')
    except x509.ExtensionNotFound:
        pass
    try:
        _require(not certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca, 'dte-ca-certificate-not-a-document-signer')
    except x509.ExtensionNotFound:
        pass
    return key


def _children(node, names):
    _require(not node.attrib and (node.text is None or not node.text.strip()), 'dte-signature-node-shape')
    _require([child.tag for child in node] == ['{%s}%s' % (DS, name) for name in names], 'dte-signature-child-order')
    _require(all(child.tail is None or not child.tail.strip() for child in node), 'dte-signature-mixed-content')


def _algorithm(node, algorithm):
    _require(dict(node.attrib) == {'Algorithm': algorithm} and len(node) == 0
        and (node.text is None or not node.text.strip()), 'dte-signature-algorithm-unsupported')


def _binary(node):
    _require(not node.attrib and len(node) == 0, 'dte-signature-leaf-shape')
    try:
        return _b64(node.text, 'dte-signature-base64')
    except CAFError:
        raise DTEError('dte-signature-base64') from None


def _canonical(node):
    return etree.tostring(node, method='c14n', exclusive=False, with_comments=False, with_tail=False)


def _verify_xml_signature(root, document, key, pin):
    signature = root[1]
    _children(signature, ('SignedInfo', 'SignatureValue', 'KeyInfo'))
    info, value, keyinfo = signature
    _children(info, ('CanonicalizationMethod', 'SignatureMethod', 'Reference'))
    canonical, algorithm, reference = info
    _algorithm(canonical, C14N)
    _algorithm(algorithm, RSA_SHA1)
    _require(dict(reference.attrib) == {'URI': '#' + document.get('ID')}, 'dte-reference-not-unique-document')
    children = list(reference)
    if children and children[0].tag == '{%s}Transforms' % DS:
        transforms = children.pop(0)
        _children(transforms, ('Transform',))
        _algorithm(transforms[0], C14N)
    _require([node.tag for node in children] == ['{%s}DigestMethod' % DS, '{%s}DigestValue' % DS], 'dte-reference-shape')
    _algorithm(children[0], SHA1)
    _require(hmac.compare_digest(_binary(children[1]), hashlib.sha1(_canonical(document)).digest()), 'dte-document-digest-mismatch')
    _children(keyinfo, ('KeyValue', 'X509Data'))
    _children(keyinfo[0], ('RSAKeyValue',))
    _children(keyinfo[0][0], ('Modulus', 'Exponent'))
    _children(keyinfo[1], ('X509Certificate',))
    _require(_binary(keyinfo[1][0]) == pin.certificate_der, 'dte-embedded-certificate-not-pinned')
    numbers = key.public_numbers()
    _require(int.from_bytes(_binary(keyinfo[0][0][0]), 'big') == numbers.n
        and int.from_bytes(_binary(keyinfo[0][0][1]), 'big') == numbers.e, 'dte-rsa-keyvalue-certificate-mismatch')
    actual = _binary(value)
    _require(len(actual) == (key.key_size + 7) // 8, 'dte-signature-size')
    try:
        key.verify(actual, _canonical(info), padding.PKCS1v15(), hashes.SHA1())
    except InvalidSignature:
        raise DTEError('dte-signature-invalid') from None


def verify_signed_dte(raw, original_caf, certificate_pin, context, *, caf_authorities=None):
    root, document, encoding = _parse(raw, signed=True)
    try:
        validate_dte_schema(root)
    except SchemaError as error:
        raise DTEError(str(error)) from None
    checked = _bound_ted(raw, document, encoding, original_caf, context, caf_authorities)
    key = _certificate(certificate_pin, context)
    _verify_xml_signature(root, document, key, certificate_pin)
    return DTEVerification(raw, context.document_id, certificate_pin.fingerprint_sha256,
        checked.caf_authority_verified, checked, context.signed_at)


def _encode(value):
    return '\n'.join(textwrap.wrap(base64.b64encode(value).decode('ascii'), 76))


def _integer_bytes(number):
    return number.to_bytes((number.bit_length() + 7) // 8, 'big')


def sign_dte(unsigned, original_caf, certificate_pin, context, private_key, *, caf_authorities):
    """Build a new Signature after schema/context/key checks; no implicit key I/O.

    Refuse an existing signature. Retain every byte of the supplied unsigned
    document, including its lexical TED/CAF. This is not an emission operation.
    """
    _require(caf_authorities is not None, 'dte-caf-authority-map-required-for-construction')
    root, document, encoding = _parse(unsigned, signed=False)
    _bound_ted(unsigned, document, encoding, original_caf, context, caf_authorities)
    key = _certificate(certificate_pin, context)
    _require(isinstance(private_key, rsa.RSAPrivateKey)
        and private_key.public_key().public_numbers() == key.public_numbers(), 'dte-private-key-does-not-match-certificate')
    signature = etree.Element('{%s}Signature' % DS, nsmap={None: DS})
    def child(parent, name, text=None, **attributes):
        node = etree.SubElement(parent, '{%s}%s' % (DS, name), **attributes)
        node.text = text
        return node
    info = child(signature, 'SignedInfo')
    child(info, 'CanonicalizationMethod', Algorithm=C14N)
    child(info, 'SignatureMethod', Algorithm=RSA_SHA1)
    reference = child(info, 'Reference', URI='#' + context.document_id)
    transforms = child(reference, 'Transforms')
    child(transforms, 'Transform', Algorithm=C14N)
    child(reference, 'DigestMethod', Algorithm=SHA1)
    child(reference, 'DigestValue', _encode(hashlib.sha1(_canonical(document)).digest()))
    value = child(signature, 'SignatureValue', _encode(b'\x00' * ((key.key_size + 7) // 8)))
    keyinfo = child(signature, 'KeyInfo')
    rsa_node = child(child(keyinfo, 'KeyValue'), 'RSAKeyValue')
    child(rsa_node, 'Modulus', _encode(_integer_bytes(key.public_numbers().n)))
    child(rsa_node, 'Exponent', _encode(_integer_bytes(key.public_numbers().e)))
    child(child(keyinfo, 'X509Data'), 'X509Certificate', _encode(certificate_pin.certificate_der))
    for node in signature.iter():
        if len(node):
            node.text = '\n'
            for item in node:
                item.tail = '\n'
    root.append(signature)
    try:
        validate_dte_schema(root)  # Before using the private signing operation.
    except SchemaError as error:
        raise DTEError(str(error)) from None
    value.text = _encode(private_key.sign(_canonical(info), padding.PKCS1v15(), hashes.SHA1()))
    endings = list(re.finditer(br'</DTE\s*>', unsigned))
    _require(len(endings) == 1, 'dte-lexical-root-ambiguity')
    index = endings[0].start()
    signed = unsigned[:index] + b'\n' + etree.tostring(signature, encoding=encoding,
        xml_declaration=False, with_tail=False) + b'\n' + unsigned[index:]
    # Reparse independently in the exact output context: namespace/encoding
    # serialization can otherwise invalidate SignedInfo without being obvious.
    verify_signed_dte(signed, original_caf, certificate_pin, context, caf_authorities=caf_authorities)
    return signed
