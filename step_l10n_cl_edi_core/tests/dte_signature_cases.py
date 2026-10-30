"""Synthetic ephemeral DTE signatures: never real certificates or emission."""
import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from .. import caf, ted, dte_schema, dte_signature as dte
from .ted_cases import synthetic_caf, synthetic_ted


def synthetic_certificate(key, *, usage=True, ca=False, begin=None, end=None):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SYNTHETIC ONLY - NOT SII'),
                     x509.NameAttribute(NameOID.SERIAL_NUMBER, '11111111-1')])
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(123456789)
        .not_valid_before(begin or datetime(2026, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(end or datetime(2027, 1, 1, tzinfo=timezone.utc))
        .add_extension(x509.KeyUsage(usage, False, False, False, False, False, False, None, None), critical=True)
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .sign(key, hashes.SHA256()))
    raw = certificate.public_bytes(serialization.Encoding.DER)
    return dte.CertificatePin(raw, hashlib.sha256(raw).hexdigest())


def synthetic_document(original, issuer_key, *, encoding='ISO-8859-1', kind=33, amount='1234',
                       document_id='SyntheticF50T33', **ted_options):
    """Build explicit fixture XML; no business model, allocation or tax engine."""
    raw_ted, _ = synthetic_ted(original, issuer_key, encoding=encoding, document_type=kind,
        amount=amount, **ted_options)
    fragment = re.sub(br'^<\?xml[^?]+\?>\s*', b'', raw_ted).decode(encoding)
    root_tag = 'Liquidacion' if kind == 43 else 'Exportaciones' if kind in ted.EXPORT_TYPES else 'Documento'
    emitter = ('<Emisor><RUTEmisor>76086428-5</RUTEmisor><RznSoc>SYNTHETIC Local</RznSoc>'
        '<GiroEmis>SYNTHETIC</GiroEmis><Acteco>123456</Acteco><DirOrigen>SYNTHETIC 1</DirOrigen>'
        '<CmnaOrigen>Santiago</CmnaOrigen></Emisor>')
    name = ted_options.get('name', 'SYNTHETIC Peñón &amp;  Hijos')
    item = ted_options.get('item', 'Cajón  Ñandú &lt;Local&gt;')
    receiver = ted_options.get('receiver', '11111111-1')
    emitted = ted_options.get('emitted', '2026-10-01')
    folio = ted_options.get('folio', 50)
    totals = '<MntExe>' + amount + '</MntExe><MntTotal>' + amount + '</MntTotal>'
    if root_tag == 'Exportaciones':
        totals = '<TpoMoneda>DOLAR USA</TpoMoneda>' + totals
    text = ('<?xml version="1.0" encoding="' + encoding + '"?>\r\n'
        '<DTE xmlns="http://www.sii.cl/SiiDte" version="1.0">\n<' + root_tag + ' ID="' + document_id + '">\n'
        '<Encabezado><IdDoc><TipoDTE>' + str(kind) + '</TipoDTE><Folio>' + str(folio) + '</Folio>'
        '<FchEmis>' + emitted + '</FchEmis></IdDoc>' + emitter
        + '<Receptor><RUTRecep>' + receiver + '</RUTRecep><RznSocRecep>' + name + '</RznSocRecep>'
        '<GiroRecep>SYNTHETIC</GiroRecep><DirRecep>SYNTHETIC 2</DirRecep><CmnaRecep>Santiago</CmnaRecep></Receptor>'
        '<Totales>' + totals + '</Totales></Encabezado>\n'
        '<Detalle><NroLinDet>1</NroLinDet>' + ('<TpoDocLiq>33</TpoDocLiq>' if kind == 43 else '')
        + '<IndExe>1</IndExe><NmbItem>' + item + '</NmbItem>'
        '<QtyItem>1</QtyItem><PrcItem>' + amount.lstrip('-') + '</PrcItem><MontoItem>' + amount + '</MontoItem></Detalle>\n'
        + fragment + '\n<TmstFirma>2026-10-01T09:03:01</TmstFirma>\n</' + root_tag + '>\n</DTE>')
    context = dte.DTEContext(document_id, ted.TEDContext('76086428-5', kind, folio,
        ted._date(emitted), receiver, etree.fromstring(('<x>' + name + '</x>').encode()).text[:40],
        Decimal(amount), etree.fromstring(('<x>' + item + '</x>').encode()).text[:40]),
        datetime(2026, 10, 1, 9, 3, 1, tzinfo=timezone(timedelta(hours=-3))))
    return text.encode(encoding), context


class DTESignatureCaseMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        cls.document_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pin = synthetic_certificate(cls.document_key)
        pem = cls.signer.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.anchor = caf.TrustAnchor(3, caf.public_key_fingerprint(cls.signer.public_key()), pem)

    def fixture(self, **options):
        original = synthetic_caf(self.signer, self.issuer_key, document_type=options.get('kind', 33),
            encoding=options.get('encoding', 'ISO-8859-1'), pretty=True)
        unsigned, context = synthetic_document(original, self.issuer_key, **options)
        return original, unsigned, context

    def signed_fixture(self, **options):
        original, unsigned, context = self.fixture(**options)
        signed = dte.sign_dte(unsigned, original, self.pin, context, self.document_key, caf_authorities={3: self.anchor})
        return original, unsigned, signed, context

    def verify(self, signed, original, context, **options):
        return dte.verify_signed_dte(signed, original, options.pop('pin', self.pin), context, **options)

    def test_real_signature_schema_context_and_authority_are_separate(self):
        original, unsigned, signed, context = self.signed_fixture()
        checked = self.verify(signed, original, context)
        self.assertEqual(checked.original_bytes(), signed)
        metadata = checked.metadata()
        for name in ('dte_xml_signature_verified', 'sii_schema_verified', 'certificate_pin_matched',
                     'certificate_time_checked', 'ted_signature_verified', 'expected_context_matched'):
            self.assertTrue(metadata[name], name)
        for name in ('caf_authority_verified', 'certificate_chain_verified', 'certificate_revocation_checked',
                     'signer_fiscal_authorization_verified', 'tax_calculation_certified', 'folio_operations_enabled',
                     'fiscal_emission_enabled', 'business_record_identity_adopted', 'sii_acceptance_certified'):
            self.assertFalse(metadata[name], name)
        self.assertTrue(self.verify(signed, original, context, caf_authorities={3: self.anchor}).caf_authority_verified)
        with self.assertRaises(dte.DTEError):
            self.verify(signed, original, context, caf_authorities={})
        self.assertNotIn('Peñón', repr(checked))
        self.assertNotIn('PRIVATE KEY', repr(checked))

    def test_encoding_entities_and_original_document_bytes_are_retained(self):
        for encoding in ('ISO-8859-1', 'UTF-8'):
            original, unsigned, signed, context = self.signed_fixture(encoding=encoding,
                name='SYNTHETIC Peñón &#38;  Hijos')
            self.assertTrue(self.verify(signed, original, context).metadata()['dte_xml_signature_verified'])
            before = re.search(br'<Documento .*?</Documento>', unsigned, re.S).group()
            self.assertEqual(before, re.search(br'<Documento .*?</Documento>', signed, re.S).group())
            self.assertIn(b'&#38;', signed)
            self.assertEqual(signed[:signed.index(b'\n<Signature')], unsigned[:unsigned.index(b'</DTE>')])

    def test_signed_body_and_signature_tampering_are_rejected(self):
        original, _, signed, context = self.signed_fixture()
        variants = [signed.replace(b'SYNTHETIC 2', b'SYNTHETIC 3'),
            signed.replace(b'<MNT>1234</MNT>', b'<MNT>1235</MNT>'),
            signed.replace(b'<Folio>50</Folio>', b'<Folio>51</Folio>'),
            signed.replace(b'<TmstFirma>2026-10-01T09:03:01', b'<TmstFirma>2026-10-01T09:03:02'),
            re.sub(br'(<SignatureValue>)[A-Za-z0-9+/]', br'\g<1>A', signed),
            signed.replace(b'<Exponent>AQAB</Exponent>', b'<Exponent>AQAC</Exponent>')]
        # Flip rather than replace-with-A, which can accidentally retain a byte.
        variants[4] = re.sub(br'(<SignatureValue>)([A-Za-z0-9+/])',
            lambda match: match[1] + (b'B' if match[2] == b'A' else b'A'), signed)
        for variant in variants:
            with self.subTest(digest=hashlib.sha256(variant).hexdigest()), self.assertRaises(dte.DTEError):
                self.verify(variant, original, context)

    def test_wrapping_duplicate_ids_signatures_and_unsafe_xml_are_rejected(self):
        original, _, signed, context = self.signed_fixture()
        variants = [signed.replace(b'<Encabezado>', b'<Encabezado Id="shadow">'),
            signed.replace(b'<Encabezado>', b'<Encabezado xml:id="shadow">'),
            signed.replace(b'<Detalle>', b'<Detalle ID="shadow">'),
            signed.replace(b'<Encabezado>', b'<!--comment--><Encabezado>'),
            signed.replace(b'<Encabezado>', b'<?unsafe pii?><Encabezado>'),
            signed.replace(b'<DTE ', b'<!DOCTYPE DTE [<!ENTITY xx SYSTEM "file:///etc/passwd">]><DTE '),
            signed.replace(b'</DTE>', b'<Documento ID="Other"/></DTE>'),
            signed.replace(b'<DTE ', b'<DTE xmlns:unused="urn:foreign" '),
            signed.replace(b'<DTE ', b'<Wrapper><DTE ').replace(b'</DTE>', b'</DTE></Wrapper>'),
            signed.replace(b'<Encabezado>', b'<Encabezado><Signature xmlns="http://www.w3.org/2000/09/xmldsig#"/>'),
            b'\x00' + signed, b'x' * (caf.MAX_XML_BYTES + 1)]
        for variant in variants:
            with self.subTest(size=len(variant)), self.assertRaises(dte.DTEError):
                self.verify(variant, original, context)

    def test_external_references_and_algorithm_negotiation_are_rejected(self):
        original, _, signed, context = self.signed_fixture()
        for ref in (b'https://sii.cl/other', b'file:///etc/passwd', b'', b'#Other', b'#xpointer(/)'):
            variant = signed.replace(b'URI="#SyntheticF50T33"', b'URI="' + ref + b'"')
            with self.subTest(ref=ref), self.assertRaises(dte.DTEError):
                self.verify(variant, original, context)
        for algorithm in (b'http://www.w3.org/TR/1999/REC-xslt-19991116',
                          b'http://www.w3.org/2000/09/xmldsig#enveloped-signature', b'urn:sha256'):
            with self.subTest(algorithm=algorithm), self.assertRaises(dte.DTEError):
                self.verify(signed.replace(dte.C14N.encode(), algorithm), original, context)

    def test_every_expected_context_field_and_signing_instant_are_bound(self):
        original, _, signed, context = self.signed_fixture()
        for name, value in dict(issuer_rut='11111111-1', document_type=34, folio=51,
                emission_date=ted._date('2026-10-02'), receiver_rut='76086428-5',
                receiver_name='OTHER', total=Decimal('1235'), first_item='OTHER').items():
            with self.subTest(name=name), self.assertRaises(dte.DTEError):
                self.verify(signed, original, replace(context, ted_context=replace(context.ted_context, **{name: value})))
        for changed in (replace(context, document_id='Other'),
                replace(context, signed_at=context.signed_at + timedelta(seconds=1)),
                replace(context, signed_at=context.signed_at.replace(tzinfo=None)),
                replace(context, signed_at=context.signed_at.replace(microsecond=1))):
            with self.assertRaises(dte.DTEError):
                self.verify(signed, original, changed)

    def test_pinned_certificate_key_usage_validity_and_key_match(self):
        original, unsigned, signed, context = self.signed_fixture()
        foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        bad_pins = [replace(self.pin, fingerprint_sha256='0' * 64), synthetic_certificate(foreign_key),
            synthetic_certificate(self.document_key, usage=False), synthetic_certificate(self.document_key, ca=True),
            synthetic_certificate(self.document_key, end=datetime(2026, 9, 30, tzinfo=timezone.utc)),
            synthetic_certificate(self.document_key, begin=datetime(2026, 10, 2, tzinfo=timezone.utc)),
            dte.CertificatePin(b'not a certificate', hashlib.sha256(b'not a certificate').hexdigest()),
            dte.CertificatePin(self.pin.certificate_der + b'TRAILING',
                hashlib.sha256(self.pin.certificate_der + b'TRAILING').hexdigest())]
        for pin in bad_pins:
            with self.subTest(pin=pin.fingerprint_sha256), self.assertRaises(dte.DTEError):
                self.verify(signed, original, context, pin=pin)
        with self.assertRaisesRegex(dte.DTEError, 'private-key-does-not-match'):
            dte.sign_dte(unsigned, original, self.pin, context, foreign_key, caf_authorities={3: self.anchor})
        # Subject is a person, issuer a company. A pin proves key identity, never
        # SII authorization to sign on behalf of that company.
        self.assertNotEqual('11111111-1', context.ted_context.issuer_rut)

    def test_no_resigning_or_construction_without_explicit_caf_anchor(self):
        original, unsigned, signed, context = self.signed_fixture()
        with self.assertRaises(dte.DTEError):
            dte.sign_dte(signed, original, self.pin, context, self.document_key, caf_authorities={3: self.anchor})
        for authorities in (None, {}):
            with self.assertRaises(dte.DTEError):
                dte.sign_dte(unsigned, original, self.pin, context, self.document_key, caf_authorities=authorities)
        # Changing only whitespace in the original CAF breaks custody binding.
        with self.assertRaises(dte.DTEError):
            self.verify(signed, original.replace(b'\r\n\t ', b'\n'), context)

    def test_official_schema_pins_and_no_external_resolution(self):
        self.assertIsInstance(dte_schema.official_schema(), etree.XMLSchema)
        root = Path(dte_schema.__file__).with_name('xml_schemas')
        files = {name: (root / name).read_bytes() for name in dte_schema.SCHEMA_SHA256}
        for name in files:
            changed = dict(files, **{name: files[name] + b'\n'})
            with self.assertRaises(dte_schema.SchemaError):
                dte_schema.official_schema(changed)
        with self.assertRaises(dte_schema.SchemaError):
            dte_schema.official_schema({})
        for url in ('https://www.sii.cl/DTE_v10.xsd', 'file:///DTE_v10.xsd', '../DTE_v10.xsd'):
            with self.assertRaises(dte_schema.SchemaError):
                dte_schema._PinnedResolver(files).resolve(url, None, None)
        original, unsigned, context = self.fixture()
        with self.assertRaisesRegex(dte.DTEError, 'sii-schema-invalid'):
            dte.sign_dte(unsigned.replace(b'<QtyItem>1</QtyItem>', b'<UNKNOWN/>'), original,
                self.pin, context, self.document_key, caf_authorities={3: self.anchor})

    def test_canonicalization_known_vector_and_exact_decimal_context(self):
        node = etree.fromstring(b'<a z="2" a="1"><b/>text&#38;tail</a>')
        self.assertEqual(dte._canonical(node), b'<a a="1" z="2"><b></b>text&amp;tail</a>')
        original, unsigned, context = self.fixture()
        with self.assertRaises(dte.DTEError):
            dte.sign_dte(unsigned, original, self.pin,
                replace(context, ted_context=replace(context.ted_context, total=1234.0)),
                self.document_key, caf_authorities={3: self.anchor})

    def test_document_liquidation_and_export_exact_amount_profiles(self):
        for kind, amount in ((33, '1234'), (34, '1234'), (46, '1234'), (52, '1234'),
                             (56, '1234'), (61, '1234'), (43, '-1234'),
                             (110, '1234.1200'), (111, '0.0001'), (112, '1234.0000')):
            with self.subTest(kind=kind, amount=amount):
                original, _, signed, context = self.signed_fixture(kind=kind, amount=amount)
                checked = self.verify(signed, original, context)
                self.assertEqual(checked.ted_verification.ted.total, Decimal(amount))
                self.assertEqual(checked.metadata()['total_text'], amount)
        original, unsigned, context = self.fixture(kind=110, amount='1234.1200')
        with self.assertRaises(dte.DTEError):
            dte.sign_dte(unsigned.replace(b'<MntTotal>1234.1200', b'<MntTotal>1234.1201'),
                original, self.pin, context, self.document_key, caf_authorities={3: self.anchor})
