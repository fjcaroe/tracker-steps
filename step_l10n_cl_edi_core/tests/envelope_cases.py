"""Ephemeral certificates/CAF only. No real submission, folio or credential."""
import base64
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from .. import caf, dte_signature as dte, envelope
from .dte_signature_cases import synthetic_certificate, synthetic_document
from .ted_cases import synthetic_caf


class EnvelopeCaseMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        cls.document_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.envelope_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.document_pin = synthetic_certificate(cls.document_key)
        cls.envelope_pin = synthetic_certificate(cls.envelope_key)
        public = cls.signer.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.anchor = caf.TrustAnchor(3, caf.public_key_fingerprint(cls.signer.public_key()), public)

    def document(self, *, index=0, kind=33, amount='1234', encoding='ISO-8859-1',
                 receiver='11111111-1', issuer='76086428-5'):
        original = synthetic_caf(self.signer, self.issuer_key, document_type=kind, encoding=encoding)
        if issuer != '76086428-5':
            original = original.replace(b'<RE>76086428-5</RE>', ('<RE>' + issuer + '</RE>').encode())
            da = re.search(br'<DA>.*?</DA>', original, re.S)[0].decode(encoding).encode('latin1')
            signature = base64.b64encode(self.signer.sign(da, padding.PKCS1v15(), hashes.SHA1()))
            original = re.sub(br'(<FRMA algoritmo="SHA1withRSA">)[^<]+', lambda match: match[1] + signature, original)
        unsigned, context = synthetic_document(original, self.issuer_key, encoding=encoding, kind=kind,
            amount=amount, folio=50 + index, document_id='SyntheticDoc' + str(index) + 'T' + str(kind), receiver=receiver)
        if issuer != '76086428-5':
            unsigned = unsigned.replace(b'<RUTEmisor>76086428-5</RUTEmisor>', ('<RUTEmisor>' + issuer + '</RUTEmisor>').encode())
            unsigned = unsigned.replace(b'<RE>76086428-5</RE>', ('<RE>' + issuer + '</RE>').encode(), 1)
            dd = re.search(br'<DD>.*?</DD>', unsigned, re.S)[0].decode(encoding).encode('latin1')
            signature = base64.b64encode(self.issuer_key.sign(dd, padding.PKCS1v15(), hashes.SHA1()))
            unsigned = re.sub(br'(<FRMT algoritmo="SHA1withRSA">)[^<]+', lambda match: match[1] + signature, unsigned)
            context = replace(context, ted_context=replace(context.ted_context, issuer_rut=issuer))
        context = replace(context, namespace_profile='sii-envelope')
        signed = dte.sign_dte(dte.prepare_unsigned_dte_for_envelope(unsigned), original,
            self.document_pin, context, self.document_key, caf_authorities={3: self.anchor})
        return envelope.SignedDTEInput(signed, original, self.document_pin, context)

    def fixture(self, *, encoding='ISO-8859-1', kinds=(33, 43, 110)):
        inputs = tuple(self.document(index=index, kind=kind, encoding=encoding,
            amount='-1234' if kind == 43 else '1234.1200' if kind == 110 else '1234')
            for index, kind in enumerate(kinds))
        context = envelope.EnvelopeContext('SyntheticSet', '76086428-5', '11111111-1', envelope.SII_RECIPIENT,
            date(2026, 9, 1), 0, datetime(2026, 10, 1, 9, 4, 0, tzinfo=timezone(timedelta(hours=-3))),
            tuple(sorted(Counter(kinds).items())), 'sii', encoding)
        return inputs, context

    def build(self, inputs, context, **options):
        return envelope.build_envelope(inputs, options.pop('pin', self.envelope_pin), context,
            options.pop('key', self.envelope_key), caf_authorities=options.pop('authorities', {3: self.anchor}))

    def verify(self, raw, inputs, context):
        return envelope.verify_envelope(raw, inputs, self.envelope_pin, context)

    def test_official_header_xsd_set_signature_and_every_embedded_signature(self):
        inputs, context = self.fixture()
        raw = self.build(inputs, context)
        checked = self.verify(raw, inputs, context)
        self.assertEqual(checked.original_bytes(), raw)
        lines = raw.splitlines()
        self.assertEqual(lines[0], b'<?xml version="1.0" encoding="ISO-8859-1"?>')
        self.assertIn(b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', lines[1])
        self.assertIn(b'xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd"', lines[1])
        metadata = checked.metadata()
        for name in ('envelope_signature_verified', 'envelope_schema_verified', 'all_document_signatures_verified',
                'all_ted_signatures_verified', 'all_original_dte_fragments_exact', 'schema_location_header_present',
                'official_sii_xml_header_verified', 'embedded_namespace_context_verified', 'certificate_subject_rut_claim_matched'):
            self.assertTrue(metadata[name], name)
        for name in ('certificate_chain_verified', 'certificate_revocation_checked', 'signer_fiscal_authorization_verified',
                'resolution_authority_verified', 'fiscal_emission_enabled', 'folio_operations_enabled',
                'sii_acceptance_certified', 'transport_profile_complete', 'caf_sii_authority_trust_certified'):
            self.assertFalse(metadata[name], name)
        self.assertEqual(metadata['document_count'], 3)
        self.assertEqual(metadata['type_counts'], ((33, 1), (43, 1), (110, 1)))
        self.assertNotIn('PRIVATE KEY', repr(checked))
        self.assertNotIn('11111111', repr(checked))

    def test_latin1_utf8_and_signed_input_fragments_are_byte_exact(self):
        for encoding in ('ISO-8859-1', 'UTF-8'):
            inputs, context = self.fixture(encoding=encoding, kinds=(33, 33))
            raw = self.build(inputs, context)
            fragments = re.findall(br'<DTE\s[^>]*>.*?</DTE\s*>', raw, re.S)
            for actual, item in zip(fragments, inputs):
                expected = re.search(br'<DTE\s[^>]*>.*?</DTE\s*>', item.original, re.S)[0]
                self.assertEqual(actual, expected)
            self.assertEqual(self.verify(raw, inputs, context).metadata()['document_sha256'],
                tuple(hashlib.sha256(item.original).hexdigest() for item in inputs))

    def test_counts_caratula_fields_and_explicit_context_are_bound(self):
        inputs, context = self.fixture(kinds=(33,))
        raw = self.build(inputs, context)
        for before, after in ((b'<NroDTE>1</NroDTE>', b'<NroDTE>2</NroDTE>'),
                (b'<TpoDTE>33</TpoDTE>', b'<TpoDTE>34</TpoDTE>'),
                (b'<RutEnvia>11111111-1</RutEnvia>', b'<RutEnvia>22222222-2</RutEnvia>'),
                (b'<NroResol>0</NroResol>', b'<NroResol>1</NroResol>'),
                (b'<FchResol>2026-09-01', b'<FchResol>2026-09-02'),
                (b'<TmstFirmaEnv>2026-10-01T09:04:00', b'<TmstFirmaEnv>2026-10-01T09:04:01')):
            with self.subTest(before=before), self.assertRaises(envelope.EnvelopeError):
                self.verify(raw.replace(before, after), inputs, context)
        for counts in (((33, 2),), ((34, 1),), ((33, 1), (33, 1)), (), ((33, 0),), ((33, True),)):
            with self.subTest(counts=counts), self.assertRaises(envelope.EnvelopeError):
                self.build(inputs, replace(context, type_counts=counts))

    def test_valid_foreign_issuer_and_counterparty_documents_cannot_be_mixed(self):
        inputs, context = self.fixture(kinds=(33, 33))
        # Fully signed foreign issuer, not a corrupted input, must still fail
        # the explicit envelope company boundary.
        foreign = self.document(index=1, issuer='11111111-1')
        dte.verify_signed_dte(foreign.original, foreign.original_caf, foreign.certificate_pin, foreign.context)
        with self.assertRaisesRegex(envelope.EnvelopeError, 'mixed-issuers'):
            self.build((inputs[0], foreign), context)
        party = replace(context, receiver_rut='11111111-1', recipient_policy='counterparty')
        self.assertTrue(self.verify(self.build(inputs, party), inputs, party).metadata()['envelope_signature_verified'])
        other_receiver = self.document(index=1, receiver='22222222-2')
        with self.assertRaisesRegex(envelope.EnvelopeError, 'counterparty-mismatch'):
            self.build((inputs[0], other_receiver), party)
        # A SII collector may contain different document recipients, without
        # inferring that any real sending or SII authorization took place.
        self.build((inputs[0], other_receiver), context)

    def test_duplicate_ids_and_duplicate_fiscal_identities_are_rejected(self):
        inputs, context = self.fixture(kinds=(33, 33))
        for repeated in ((inputs[0], inputs[0]),):
            with self.assertRaises(envelope.EnvelopeError):
                self.build(repeated, context)
        with self.assertRaises(envelope.EnvelopeError):
            self.build(inputs, replace(context, set_id=inputs[0].context.document_id))
        # Distinct XML IDs are insufficient if issuer/type/folio repeats.
        original = inputs[0]
        unsigned, selected = synthetic_document(original.original_caf, self.issuer_key,
            document_id='AnotherXmlId', folio=50)
        selected = replace(selected, namespace_profile='sii-envelope')
        signed = dte.sign_dte(dte.prepare_unsigned_dte_for_envelope(unsigned), original.original_caf,
            self.document_pin, selected, self.document_key, caf_authorities={3: self.anchor})
        repeated = envelope.SignedDTEInput(signed, original.original_caf, self.document_pin, selected)
        with self.assertRaisesRegex(envelope.EnvelopeError, 'duplicate-document-identity'):
            self.build((inputs[0], repeated), context)

    def test_wrapping_external_references_header_and_algorithm_tampering_fail(self):
        inputs, context = self.fixture(kinds=(33,))
        raw = self.build(inputs, context)
        variants = [raw.replace(b'URI="#SyntheticSet"', b'URI="https://www.sii.cl/other"'),
            raw.replace(b'URI="#SyntheticSet"', b'URI="#SyntheticDoc0T33"'),
            raw.replace(b'<SetDTE ID=', b'<SetDTE Id='),
            raw.replace(b'<Caratula ', b'<?unsafe node?><Caratula '),
            raw.replace(b'<Caratula ', b'<!--unsafe--><Caratula '),
            raw.replace(b'<EnvioDTE ', b'<!DOCTYPE EnvioDTE [<!ENTITY xx SYSTEM "file:///etc/passwd">]><EnvioDTE '),
            raw.replace(b'<EnvioDTE ', b'<Wrapper><EnvioDTE ').replace(b'</EnvioDTE>', b'</EnvioDTE></Wrapper>'),
            raw.replace(b'</SetDTE>', b'<Caratula version="1.0"/></SetDTE>'),
            raw.replace(b'EnvioDTE_v10.xsd', b'https://foreign.example/schema.xsd'),
            raw.replace(b'xsi:schemaLocation=', b'xsi:foreignLocation='),
            b'\n' + raw, raw.replace(b' xmlns:xsi=', b'\nxmlns:xsi=', 1),
            raw.replace(dte.RSA_SHA1.encode(), b'urn:another-algorithm')]
        for variant in variants:
            with self.subTest(sha=hashlib.sha256(variant).hexdigest()), self.assertRaises(envelope.EnvelopeError):
                self.verify(variant, inputs, context)

    def test_tampered_or_reordered_documents_never_return_a_usable_envelope(self):
        inputs, context = self.fixture(kinds=(33, 110))
        raw = self.build(inputs, context)
        for variant in (raw.replace(b'SYNTHETIC 2', b'SYNTHETIC 3'),
                        raw.replace(b'<MNT>1234</MNT>', b'<MNT>1235</MNT>')):
            with self.assertRaises(envelope.EnvelopeError):
                self.verify(variant, inputs, context)
        with self.assertRaises(envelope.EnvelopeError):
            self.verify(raw, tuple(reversed(inputs)), context)
        altered = replace(inputs[0], original=inputs[0].original.replace(b'SYNTHETIC 2', b'SYNTHETIC 3'))
        with self.assertRaises(envelope.EnvelopeError):
            self.build((altered, inputs[1]), context)
        # SignatureValue of the outer envelope must also verify, independently
        # of input/body byte matching and all inner document signatures.
        values = list(re.finditer(br'(<SignatureValue>)([A-Za-z0-9+/])', raw))
        found = values[-1]
        tampered = raw[:found.start(2)] + (b'B' if found[2] == b'A' else b'A') + raw[found.end(2):]
        with self.assertRaises(envelope.EnvelopeError):
            self.verify(tampered, inputs, context)

    def test_resolution_times_recipient_policy_and_certificate_claims_are_explicit(self):
        inputs, context = self.fixture(kinds=(33,))
        for changed in (replace(context, signed_at=inputs[0].context.signed_at - timedelta(seconds=1)),
                replace(context, signed_at=context.signed_at.replace(tzinfo=None)),
                replace(context, resolution_date=date(2026, 10, 2)), replace(context, resolution_number=-1),
                replace(context, resolution_number=0.0), replace(context, receiver_rut='11111111-1'),
                replace(context, signer_rut='22222222-2'), replace(context, recipient_policy='infer')):
            with self.assertRaises(envelope.EnvelopeError):
                self.build(inputs, changed)
        with self.assertRaises(envelope.EnvelopeError):
            self.build(inputs, context, key=self.document_key)
        for claims in ([], ['22222222-2'], ['11111111-1', '11111111-1']):
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SYNTHETIC NOT SII')]
                + [x509.NameAttribute(NameOID.SERIAL_NUMBER, value) for value in claims])
            certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(self.envelope_key.public_key()).serial_number(23456789)
                .not_valid_before(datetime(2026, 1, 1, tzinfo=timezone.utc))
                .not_valid_after(datetime(2027, 1, 1, tzinfo=timezone.utc)).sign(self.envelope_key, hashes.SHA256()))
            data = certificate.public_bytes(serialization.Encoding.DER)
            pin = dte.CertificatePin(data, hashlib.sha256(data).hexdigest())
            with self.subTest(claims=len(claims)), self.assertRaises(envelope.EnvelopeError):
                self.build(inputs, context, pin=pin)

    def test_resource_encoding_and_explicit_authority_guards_fail_closed(self):
        inputs, context = self.fixture(kinds=(33,))
        for items in ((), list(inputs), inputs * 2001):
            with self.assertRaises(envelope.EnvelopeError):
                self.build(items, context)
        for authorities in (None, {}):
            with self.assertRaises(envelope.EnvelopeError):
                self.build(inputs, context, authorities=authorities)
        foreign_encoding = self.document(encoding='UTF-8')
        with self.assertRaisesRegex(envelope.EnvelopeError, 'encoding-mismatch-no-transcoding'):
            self.build((foreign_encoding,), context)
        for raw in (b'not XML', b'\x00', b'x' * (envelope.MAX_ENVELOPE_BYTES + 1)):
            with self.assertRaises(envelope.EnvelopeError):
                self.verify(raw, inputs, context)

    def test_standalone_signed_documents_are_not_rewritten_for_inherited_namespace(self):
        inputs, context = self.fixture(kinds=(33,))
        source = inputs[0]
        unsigned, selected = synthetic_document(source.original_caf, self.issuer_key, document_id='Standalone')
        standalone = dte.sign_dte(unsigned, source.original_caf, self.document_pin, selected,
            self.document_key, caf_authorities={3: self.anchor})
        item = envelope.SignedDTEInput(standalone, source.original_caf, self.document_pin, selected)
        original_hash = hashlib.sha256(item.original).hexdigest()
        with self.assertRaisesRegex(envelope.EnvelopeError, 'not-prepared-for-inherited-xsi'):
            self.build((item,), context)
        self.assertEqual(hashlib.sha256(item.original).hexdigest(), original_hash)
        with self.assertRaises(envelope.EnvelopeError):
            self.build((replace(item, context=replace(selected, namespace_profile='sii-envelope')),), context)
