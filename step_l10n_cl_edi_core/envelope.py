"""Offline EnvioDTE XMLDSig/XSD contract with immutable signed DTE inputs.

The official xsi/schemaLocation header is mandatory. Its namespace must be
prepared explicitly BEFORE each NEW input DTE is signed, since it is inherited
by inclusive C14N. Incompatible signed/legacy inputs are rejected unchanged.
"""
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime
import hashlib
from pathlib import Path
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from . import dte_schema, dte_signature as dte, ted
from .caf import CAFError, SII_NAMESPACE, normalize_rut


MAX_ENVELOPE_BYTES = 20 * 1024 * 1024  # Local resource guard, not a SII limit.
SII_RECIPIENT = '60803000-K'
NS = '{' + SII_NAMESPACE + '}'


class EnvelopeError(ValueError):
    """Codes only; never XML, personal data, certificate bodies or secrets."""


def _require(value, code):
    if not value:
        raise EnvelopeError(code)


@dataclass(frozen=True)
class SignedDTEInput:
    original: bytes = field(repr=False)
    original_caf: bytes = field(repr=False)
    certificate_pin: dte.CertificatePin = field(repr=False)
    context: dte.DTEContext = field(repr=False)


@dataclass(frozen=True)
class EnvelopeContext:
    set_id: str
    issuer_rut: str = field(repr=False)
    signer_rut: str = field(repr=False)
    receiver_rut: str = field(repr=False)
    resolution_date: date
    resolution_number: int
    signed_at: datetime
    type_counts: tuple
    recipient_policy: str
    encoding: str = 'ISO-8859-1'


@dataclass(frozen=True)
class EnvelopeVerification:
    _original: bytes = field(repr=False)
    _document_hashes: tuple = field(repr=False)
    context: EnvelopeContext
    certificate_sha256: str

    def original_bytes(self):
        return self._original

    def metadata(self):
        return {'envelope_sha256': hashlib.sha256(self._original).hexdigest(),
            'set_id': self.context.set_id, 'document_count': len(self._document_hashes),
            'type_counts': self.context.type_counts, 'document_sha256': self._document_hashes,
            'certificate_sha256': self.certificate_sha256, 'envelope_signature_verified': True,
            'envelope_schema_verified': True, 'all_document_signatures_verified': True,
            'all_ted_signatures_verified': True, 'all_original_dte_fragments_exact': True,
            'certificate_subject_rut_claim_matched': True,
            'schema_location_header_present': True, 'official_sii_xml_header_verified': True,
            'embedded_namespace_context_verified': True, 'transport_profile_complete': False,
            'certificate_chain_verified': False, 'certificate_revocation_checked': False,
            'signer_fiscal_authorization_verified': False, 'resolution_authority_verified': False,
            'caf_sii_authority_trust_certified': False,
            'fiscal_emission_enabled': False, 'folio_operations_enabled': False,
            'sii_acceptance_certified': False}


def _context(context, inputs):
    _require(isinstance(context, EnvelopeContext), 'envelope-context-required')
    _require(type(inputs) is tuple and 1 <= len(inputs) <= 2000
        and all(isinstance(item, SignedDTEInput) for item in inputs), 'envelope-explicit-documents-required')
    _require(all(type(item.original) is bytes for item in inputs)
        and sum(len(item.original) for item in inputs) <= MAX_ENVELOPE_BYTES - 16384, 'envelope-input-size-or-type')
    for item in inputs:
        try:
            dte._context(item.context)
        except dte.DTEError as error:
            raise EnvelopeError('envelope-input-' + str(error)) from None
        _require(item.context.namespace_profile == 'sii-envelope', 'envelope-input-not-prepared-for-inherited-xsi')
    _require(type(context.set_id) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,79}', context.set_id), 'envelope-set-id')
    _require(type(context.signed_at) is datetime and context.signed_at.utcoffset() is not None
        and context.signed_at.microsecond == 0, 'envelope-signature-instant-required')
    _require(type(context.resolution_date) is date and date(2000, 1, 1) <= context.resolution_date
        <= min(date(2050, 12, 31), context.signed_at.date()), 'envelope-resolution-date')
    _require(type(context.resolution_number) is int and 0 <= context.resolution_number <= 999999, 'envelope-resolution-number')
    _require(context.encoding in ('ISO-8859-1', 'UTF-8'), 'envelope-encoding')
    try:
        for value in (context.issuer_rut, context.signer_rut, context.receiver_rut):
            _require(type(value) is str and normalize_rut(value) == value, 'envelope-rut-format')
    except CAFError:
        raise EnvelopeError('envelope-rut-format') from None
    _require(context.recipient_policy in ('sii', 'counterparty'), 'envelope-recipient-policy')
    if context.recipient_policy == 'sii':
        _require(context.receiver_rut == SII_RECIPIENT, 'envelope-sii-recipient-mismatch')
    _require(type(context.type_counts) is tuple and 1 <= len(context.type_counts) <= 20
        and all(type(row) is tuple and len(row) == 2 and all(type(value) is int for value in row)
            and 1 <= row[1] <= 2000 for row in context.type_counts), 'envelope-type-counts')
    _require(context.type_counts == tuple(sorted(dict(context.type_counts).items())), 'envelope-duplicate-or-unordered-type-counts')


def _fragment(item, context):
    try:
        _, _, encoding = dte._parse(item.original, signed=True, namespace_profile=item.context.namespace_profile)
    except dte.DTEError as error:
        raise EnvelopeError('envelope-input-' + str(error)) from None
    _require(encoding == context.encoding, 'envelope-input-encoding-mismatch-no-transcoding')
    match = re.fullmatch(br'\s*(?:<\?xml[^?]*\?>\s*)?(<DTE\s[^>]*>.*</DTE\s*>)\s*', item.original, re.S)
    _require(match is not None, 'envelope-input-fragment-ambiguous')
    return match[1]


def _schema():
    folder = Path(dte_schema.__file__).with_name('xml_schemas')
    files = {name: (folder / name).read_bytes() for name in dte_schema.SCHEMA_SHA256}
    dte_schema.official_schema(files)  # Validates all immutable public pins.
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    parser.resolvers.add(dte_schema._PinnedResolver(files))
    try:
        root = etree.fromstring(files['EnvioDTE_v10.xsd'], parser, base_url='memory:///EnvioDTE_v10.xsd')
        return etree.XMLSchema(root)
    except (etree.XMLSyntaxError, etree.XMLSchemaParseError):
        raise EnvelopeError('envelope-schema-compile-failed') from None


def _parse(raw, context):
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_ENVELOPE_BYTES, 'envelope-size-or-type')
    _require(b'<!' not in raw and b'\x00' not in raw, 'envelope-declaration-forbidden')
    lines = raw.splitlines()
    _require(len(lines) >= 2 and lines[0] == ('<?xml version="1.0" encoding="' + context.encoding + '"?>').encode('ascii')
        and re.fullmatch(br'<EnvioDTE\s[^>]*>', lines[1]) is not None, 'envelope-first-two-lines-header-required')
    try:
        root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, load_dtd=False,
            no_network=True, huge_tree=False, remove_comments=False, remove_pis=False))
    except (ValueError, etree.XMLSyntaxError):
        raise EnvelopeError('envelope-xml-invalid') from None
    _require(root.getprevious() is None and root.getnext() is None
        and root.tag == NS + 'EnvioDTE' and root.nsmap == {None: SII_NAMESPACE, 'xsi': dte.XSI}
        and root.prefix is None and dict(root.attrib) == {'version': '1.0',
            '{%s}schemaLocation' % dte.XSI: SII_NAMESPACE + ' EnvioDTE_v10.xsd'}, 'envelope-root-official-header-profile')
    encoding = root.getroottree().docinfo.encoding.upper().replace('_', '-')
    _require(encoding == context.encoding, 'envelope-encoding-context-mismatch')
    _require(len(root) == 2 and root[0].tag == NS + 'SetDTE'
        and root[1].tag == '{%s}Signature' % dte.DS, 'envelope-single-set-and-signature-required')
    node = root[0]
    _require(dict(node.attrib) == {'ID': context.set_id} and len(node) >= 2
        and node[0].tag == NS + 'Caratula' and dict(node[0].attrib) == {'version': '1.0'}
        and all(child.tag == NS + 'DTE' for child in list(node)[1:]), 'envelope-set-shape')
    for element in root.iter():
        _require(isinstance(element.tag, str) and etree.QName(element).namespace in (SII_NAMESPACE, dte.DS)
            and set(element.nsmap.values()) <= {SII_NAMESPACE, dte.DS, dte.XSI}, 'envelope-namespace-or-node')
        if etree.QName(element).namespace == SII_NAMESPACE:
            _require(element.prefix is None, 'envelope-prefixed-data-unsupported')
        for value in (element.text, element.tail):
            if value:
                try:
                    value.encode('latin1')
                except UnicodeError:
                    raise EnvelopeError('envelope-text-not-latin1') from None
    try:
        _require(_schema().validate(root), 'envelope-sii-schema-invalid')
    except dte_schema.SchemaError as error:
        raise EnvelopeError(str(error)) from None
    return root, node


def _caratula(node, context):
    names = ('RutEmisor', 'RutEnvia', 'RutReceptor', 'FchResol', 'NroResol', 'TmstFirmaEnv')
    expected = (context.issuer_rut, context.signer_rut, context.receiver_rut,
        context.resolution_date.isoformat(), str(context.resolution_number),
        context.signed_at.replace(tzinfo=None).isoformat(timespec='seconds'))
    caratula = node[0]
    _require([child.tag for child in caratula] == [NS + name for name in names]
        + [NS + 'SubTotDTE'] * len(context.type_counts), 'envelope-caratula-shape')
    for child, value in zip(list(caratula)[:6], expected):
        _require(not child.attrib and len(child) == 0 and child.text == value, 'envelope-caratula-context-mismatch')
    for subtotal, (kind, count) in zip(list(caratula)[6:], context.type_counts):
        _require(not subtotal.attrib and [child.tag for child in subtotal] == [NS + 'TpoDTE', NS + 'NroDTE']
            and all(not child.attrib and len(child) == 0 for child in subtotal)
            and (subtotal[0].text, subtotal[1].text) == (str(kind), str(count)), 'envelope-counts-context-mismatch')


def _documents(raw, node, inputs, context, authorities):
    fragments = re.findall(br'<DTE\s[^>]*>.*?</DTE\s*>', raw, re.S)
    _require(len(fragments) == len(inputs) == len(node) - 1, 'envelope-document-count-mismatch')
    identities, ids, kinds, originals = set(), {context.set_id}, Counter(), []
    for fragment, element, item in zip(fragments, list(node)[1:], inputs):
        _require(fragment == _fragment(item, context), 'envelope-original-document-bytes-mismatch')
        try:
            result = dte.verify_signed_dte(item.original, item.original_caf, item.certificate_pin,
                item.context, caf_authorities=authorities)
            # Verify again on the actual nested element, including ancestor
            # namespace context; isolation alone cannot prove an embedded sig.
            key = dte._certificate(item.certificate_pin, item.context)
            dte._verify_xml_signature(element, element[0], key, item.certificate_pin)
        except dte.DTEError as error:
            raise EnvelopeError('envelope-document-' + str(error)) from None
        identity = result.ted_verification.ted
        _require(identity.issuer_rut == context.issuer_rut, 'envelope-mixed-issuers')
        if context.recipient_policy == 'counterparty':
            _require(identity.receiver_rut == context.receiver_rut, 'envelope-counterparty-mismatch')
        _require(identity.emission_date >= context.resolution_date and item.context.signed_at <= context.signed_at,
            'envelope-before-resolution-or-document-signature')
        fiscal_id = (identity.issuer_rut, identity.document_type, identity.folio)
        _require(fiscal_id not in identities and item.context.document_id not in ids, 'envelope-duplicate-document-identity')
        identities.add(fiscal_id)
        ids.add(item.context.document_id)
        kinds[identity.document_type] += 1
        originals.append(hashlib.sha256(item.original).hexdigest())
    _require(tuple(sorted(kinds.items())) == context.type_counts, 'envelope-counts-not-actual-documents')
    return tuple(originals)


def _signer_key(pin, context, inputs):
    try:
        key = dte._certificate(pin, replace(inputs[0].context, document_id=context.set_id, signed_at=context.signed_at))
    except dte.DTEError as error:
        raise EnvelopeError('envelope-' + str(error)) from None
    certificate = x509.load_der_x509_certificate(pin.certificate_der)
    # Explicit admitted certificate profile, not a universal Chilean X509
    # identity resolver and not proof that SII trusts this claim/certificate.
    claims = certificate.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
    _require(len(claims) == 1 and claims[0].value == context.signer_rut, 'envelope-certificate-subject-rut-claim-mismatch')
    return key


def verify_envelope(raw, inputs, certificate_pin, context, *, caf_authorities=None):
    _context(context, inputs)
    root, node = _parse(raw, context)
    _caratula(node, context)
    originals = _documents(raw, node, inputs, context, caf_authorities)
    key = _signer_key(certificate_pin, context, inputs)
    try:
        dte._verify_xml_signature(root, node, key, certificate_pin)
    except dte.DTEError as error:
        raise EnvelopeError('envelope-' + str(error)) from None
    return EnvelopeVerification(raw, originals, context, certificate_pin.fingerprint_sha256)


def build_envelope(inputs, certificate_pin, context, private_key, *, caf_authorities):
    """Create only a new envelope/Signature. No DTE re-signing or persistence."""
    _context(context, inputs)
    _require(caf_authorities is not None, 'envelope-caf-authorities-required-for-construction')
    key = _signer_key(certificate_pin, context, inputs)
    _require(isinstance(private_key, rsa.RSAPrivateKey)
        and private_key.public_key().public_numbers() == key.public_numbers(), 'envelope-private-key-certificate-mismatch')
    root = etree.Element(NS + 'EnvioDTE', nsmap={None: SII_NAMESPACE, 'xsi': dte.XSI}, version='1.0')
    node = etree.SubElement(root, NS + 'SetDTE', ID=context.set_id)
    caratula = etree.SubElement(node, NS + 'Caratula', version='1.0')
    values = (('RutEmisor', context.issuer_rut), ('RutEnvia', context.signer_rut),
        ('RutReceptor', context.receiver_rut), ('FchResol', context.resolution_date.isoformat()),
        ('NroResol', str(context.resolution_number)),
        ('TmstFirmaEnv', context.signed_at.replace(tzinfo=None).isoformat(timespec='seconds')))
    for name, value in values:
        etree.SubElement(caratula, NS + name).text = value
    for kind, count in context.type_counts:
        subtotal = etree.SubElement(caratula, NS + 'SubTotDTE')
        etree.SubElement(subtotal, NS + 'TpoDTE').text = str(kind)
        etree.SubElement(subtotal, NS + 'NroDTE').text = str(count)
    header = etree.tostring(caratula, encoding=context.encoding, xml_declaration=False)
    unsigned = ('<?xml version="1.0" encoding="' + context.encoding + '"?>\n'
        '<EnvioDTE xmlns="' + SII_NAMESPACE + '" xmlns:xsi="' + dte.XSI + '" '
        'xsi:schemaLocation="' + SII_NAMESPACE + ' EnvioDTE_v10.xsd" version="1.0">\n'
        '<SetDTE ID="' + context.set_id + '">\n').encode('ascii')
    unsigned += header + b'\n' + b'\n'.join(_fragment(item, context) for item in inputs) + b'\n</SetDTE>\n</EnvioDTE>'
    # Signature placeholders make the official signed envelope schema available
    # before using the private signing operation.
    root = etree.fromstring(unsigned)
    node = root[0]
    signature = etree.SubElement(root, '{%s}Signature' % dte.DS, nsmap={None: dte.DS})
    def child(parent, name, text=None, **attrs):
        element = etree.SubElement(parent, '{%s}%s' % (dte.DS, name), **attrs)
        element.text = text
        return element
    info = child(signature, 'SignedInfo')
    child(info, 'CanonicalizationMethod', Algorithm=dte.C14N)
    child(info, 'SignatureMethod', Algorithm=dte.RSA_SHA1)
    reference = child(info, 'Reference', URI='#' + context.set_id)
    child(child(reference, 'Transforms'), 'Transform', Algorithm=dte.C14N)
    child(reference, 'DigestMethod', Algorithm=dte.SHA1)
    child(reference, 'DigestValue', dte._encode(hashlib.sha1(dte._canonical(node)).digest()))
    value = child(signature, 'SignatureValue', dte._encode(b'\x00' * ((key.key_size + 7) // 8)))
    keyinfo = child(signature, 'KeyInfo')
    rsa_node = child(child(keyinfo, 'KeyValue'), 'RSAKeyValue')
    child(rsa_node, 'Modulus', dte._encode(dte._integer_bytes(key.public_numbers().n)))
    child(rsa_node, 'Exponent', dte._encode(dte._integer_bytes(key.public_numbers().e)))
    child(child(keyinfo, 'X509Data'), 'X509Certificate', dte._encode(certificate_pin.certificate_der))
    for element in signature.iter():
        if len(element):
            element.text = '\n'
            for item in element:
                item.tail = '\n'
    # Serialize only the new Signature. Every received DTE fragment stays exact.
    placeholder = unsigned.replace(b'</EnvioDTE>', etree.tostring(signature,
        encoding=context.encoding, xml_declaration=False, with_tail=False) + b'\n</EnvioDTE>')
    parsed, set_node = _parse(placeholder, context)
    _caratula(set_node, context)
    _documents(placeholder, set_node, inputs, context, caf_authorities)
    value.text = dte._encode(private_key.sign(dte._canonical(info), padding.PKCS1v15(), hashes.SHA1()))
    signed = unsigned.replace(b'</EnvioDTE>', etree.tostring(signature,
        encoding=context.encoding, xml_declaration=False, with_tail=False) + b'\n</EnvioDTE>')
    verify_envelope(signed, inputs, certificate_pin, context, caf_authorities=caf_authorities)
    return signed
