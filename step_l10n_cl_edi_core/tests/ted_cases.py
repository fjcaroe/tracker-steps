"""Synthetic ephemeral TED/CAF keys only; no SII credential or real issuance."""
import base64
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import re

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .. import caf, ted


def _b64number(value):
    return base64.b64encode(value.to_bytes((value.bit_length() + 7) // 8, 'big')).decode()


def synthetic_caf(signer, issuer_key, *, document_type=33, encoding='ISO-8859-1', pretty=False):
    numbers = issuer_key.public_key().public_numbers()
    payload = ('<DA><RE>76086428-5</RE><RS>SYNTHETIC Ñandú &amp; Local  CAF</RS><TD>'
        + str(document_type) + '</TD><RNG><D>50</D><H>101</H></RNG><FA>2026-10-01</FA>'
        '<RSAPK><M>' + _b64number(numbers.n) + '</M><E>' + _b64number(numbers.e)
        + '</E></RSAPK><IDK>3</IDK></DA>')
    signature = signer.sign(payload.encode('latin1'), padding.PKCS1v15(), hashes.SHA1())
    body = '<CAF version="1.0">' + payload + '<FRMA algoritmo="SHA1withRSA">' + base64.b64encode(signature).decode() + '</FRMA></CAF>'
    if pretty:
        body = body.replace('><', '>\r\n\t <')
    return ('<?xml version="1.0" encoding="' + encoding + '"?>\r\n' + body).encode(encoding)


def synthetic_ted(original_caf, issuer_key, *, document_type=33, folio=50,
                  emitted='2026-10-01', receiver='11111111-1',
                  name='SYNTHETIC Peñón &amp;  Hijos', amount='1234',
                  item='Cajón  Ñandú &lt;Local&gt;', timestamp='2026-10-01T09:03:00',
                  encoding='ISO-8859-1', pretty=False, namespace=False):
    # The fixture signs its own literal DD, never a payload supplied by the
    # verifier. Preserve the actual CAF fragment; compact only for its digest.
    declaration = re.match(br'<\?xml[^?]+encoding=["\']([^"\']+)["\'][^?]*\?>', original_caf)
    source_encoding = declaration[1].decode() if declaration else 'UTF-8'
    original_text = original_caf.decode(source_encoding)
    public = re.search(r'<CAF\s[^>]*>.*?</CAF\s*>', original_text, re.S).group()
    body = ('<DD><RE>76086428-5</RE><TD>' + str(document_type) + '</TD><F>' + str(folio)
        + '</F><FE>' + emitted + '</FE><RR>' + receiver + '</RR><RSR>' + name
        + '</RSR><MNT>' + amount + '</MNT><IT1>' + item + '</IT1>' + public
        + '<TSTED>' + timestamp + '</TSTED></DD>')
    expected_digest_input = re.sub(r'>[\t\r\n ]+<', '><', body).encode('latin1')
    signature = issuer_key.sign(expected_digest_input, padding.PKCS1v15(), hashes.SHA1())
    if pretty:
        # Outside CAF only: the embedded authorization must retain its bytes.
        body = body.replace('<DD><RE>', '<DD>\r\n\t<RE>').replace('<TSTED>', '\r\n\t<TSTED>')
    root = '<TED' + (' xmlns="http://www.sii.cl/SiiDte"' if namespace else '') + ' version="1.0">'
    result = root + body + '<FRMT algoritmo="SHA1withRSA">' + base64.b64encode(signature).decode() + '</FRMT></TED>'
    return ('<?xml version="1.0" encoding="' + encoding + '"?>\r\n' + result).encode(encoding), expected_digest_input


class TEDCaseMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        pem = cls.signer.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.anchor = caf.TrustAnchor(3, caf.public_key_fingerprint(cls.signer.public_key()), pem)

    def fixture(self, *, document_type=33, encoding='ISO-8859-1', caf_pretty=False, **options):
        original = synthetic_caf(self.signer, self.issuer_key, document_type=document_type,
            encoding=encoding, pretty=caf_pretty)
        raw, signed = synthetic_ted(original, self.issuer_key, document_type=document_type, encoding=encoding, **options)
        return original, raw, signed

    def test_real_frmt_signature_and_authority_are_separate(self):
        original, raw, signed = self.fixture()
        checked = ted.check_ted_against_caf(raw, original)
        self.assertTrue(checked.metadata()['ted_signature_verified'])
        self.assertFalse(checked.metadata()['caf_authority_verified'])
        self.assertFalse(checked.metadata()['folio_operations_enabled'])
        self.assertFalse(checked.metadata()['sii_acceptance_certified'])
        verified = ted.verify_ted(raw, {3: self.anchor})
        self.assertTrue(verified.caf_authority_verified)
        self.assertEqual(verified.ted._signed_data, signed)
        with self.assertRaisesRegex(ted.TEDError, '^ted-caf-authority-untrusted$'):
            ted.verify_ted(raw, {})
        # A valid issuer signature cannot turn an untrusted/invalid FRMA into
        # authority authentication. The custody-only result must stay False.
        untrusted = re.sub(br'(<FRMA algoritmo="SHA1withRSA">)[^<]+',
            lambda match: match[1] + base64.b64encode(b'SYNTHETIC invalid authority signature'), original)
        untrusted_ted, _ = synthetic_ted(untrusted, self.issuer_key)
        self.assertFalse(ted.check_ted_against_caf(untrusted_ted, untrusted).caf_authority_verified)
        with self.assertRaisesRegex(ted.TEDError, '^ted-caf-signature-invalid$'):
            ted.verify_ted(untrusted_ted, {3: self.anchor})

    def test_original_bytes_latin1_utf8_entities_spaces_and_safe_repr(self):
        for options in ({}, {'pretty': True, 'caf_pretty': True}, {'namespace': True},
                        {'encoding': 'UTF-8', 'pretty': True}):
            with self.subTest(options=options):
                original, raw, signed = self.fixture(**options)
                parsed = ted.verify_ted(raw, {3: self.anchor}).ted
                self.assertEqual(parsed.original_bytes(), raw)
                self.assertEqual(parsed._signed_data, signed)
                self.assertEqual(parsed.public_caf_bytes(), caf.parse_caf(original).public_caf_bytes())
                self.assertIn('Peñón &amp;  Hijos'.encode('latin1'), signed)
                self.assertEqual(parsed.receiver_name, 'SYNTHETIC Peñón &  Hijos')
                self.assertEqual(parsed.first_item, 'Cajón  Ñandú <Local>')
                for secret in ('Peñón', '11111111', '<DD>', 'PRIVATE KEY'):
                    self.assertNotIn(secret, repr(parsed))
        _, raw, signed = self.fixture(name='SYNTHETIC Peñón &#38;  Hijos')
        self.assertEqual(ted.verify_ted(raw, {3: self.anchor}).ted._signed_data, signed)
        self.assertIn(b'&#38;', signed)

    def test_signed_values_wrong_key_and_signature_algorithm_fail(self):
        original, raw, _ = self.fixture()
        for before, after in ((b'<MNT>1234</MNT>', b'<MNT>1235</MNT>'),
                              (b'  Hijos', b' Hijos'), (b'<RR>11111111-1</RR>', b'<RR>76086428-5</RR>')):
            with self.subTest(before=before), self.assertRaisesRegex(ted.TEDError, '^ted-signature-invalid$'):
                ted.check_ted_against_caf(raw.replace(before, after), original)
        with self.assertRaisesRegex(ted.TEDError, '^ted-signature-algorithm$'):
            ted.verify_ted(raw.replace(b'<FRMT algoritmo="SHA1withRSA"', b'<FRMT algoritmo="SHA256withRSA"'), {3: self.anchor})
        foreign = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        forged, _ = synthetic_ted(original, foreign)
        with self.assertRaisesRegex(ted.TEDError, '^ted-signature-invalid$'):
            ted.verify_ted(forged, {3: self.anchor})

    def test_unsafe_xml_wrapping_duplicates_namespaces_and_size_fail_closed(self):
        _, raw, _ = self.fixture()
        variants = [raw.replace(b'<DD>', b'<DD id="wrapper">'),
            raw.replace(b'<F>50</F>', b'<F>50</F><F>51</F>'),
            raw.replace(b'</DD>', b'<UNKNOWN>1</UNKNOWN></DD>'),
            raw.replace(b'<TED ', b'<WRAPPER><TED ').replace(b'</TED>', b'</TED></WRAPPER>'),
            raw.replace(b'<DD>', b'<!--comment--><DD>'),
            raw.replace(b'<DD>', b'<?unsafe node?><DD>'),
            raw.replace(b'<DD>', b'<!DOCTYPE TED [<!ENTITY x SYSTEM "file:///etc/passwd">]><DD>'),
            raw.replace(b'<TED ', b'<TED xmlns="urn:foreign" '),
            raw.replace(b'<TED ', b'<s:TED xmlns:s="http://www.sii.cl/SiiDte" ').replace(b'</TED>', b'</s:TED>'),
            raw.replace(b'<TED ', b'<TED xmlns:x="urn:unused" '),
            b'\x00' + raw, b'<broken SENSITIVE_RECEIVER', b'x' * (caf.MAX_XML_BYTES + 1)]
        for variant in variants:
            with self.subTest(length=len(variant)), self.assertRaises(ted.TEDError) as caught:
                ted.parse_ted(variant)
            self.assertNotIn('SENSITIVE_RECEIVER', str(caught.exception))

    def test_caf_identity_folio_date_and_timestamp_boundaries(self):
        for options in ({'folio': 49}, {'folio': 102}, {'folio': 0}, {'folio': 10**10},
                        {'emitted': '2026-09-30'}, {'emitted': '2026-02-30'},
                        {'emitted': '2051-01-01'}, {'timestamp': '2026-10-01T24:00:00'},
                        {'timestamp': '2026-10-01T00:00:00Z'}, {'name': 'x' * 41}):
            _, raw, _ = self.fixture(**options)
            with self.subTest(options=options), self.assertRaises(ted.TEDError):
                ted.parse_ted(raw)
        for folio in (50, 101):
            _, raw, _ = self.fixture(folio=folio)
            self.assertEqual(ted.verify_ted(raw, {3: self.anchor}).ted.folio, folio)

    def test_ordinary_liquidation_and_export_amounts_are_exact(self):
        for kind, amount in ((33, '0'), (33, str(2**64 - 1)), (43, '-1234'),
                             (110, '0.0001'), (111, '99999999999999.9999'), (112, '123.4500')):
            _, raw, _ = self.fixture(document_type=kind, amount=amount)
            value = ted.verify_ted(raw, {3: self.anchor}).ted
            self.assertIsInstance(value.total, Decimal)
            self.assertEqual(value.total, Decimal(amount))
            self.assertEqual(value.total_text, amount)
        for kind, amount in ((33, '-1'), (33, '0.1'), (33, str(2**64)),
                             (43, '-1000000000000000000'), (110, '1.00001'),
                             (110, '-0.0001'), (110, '100000000000000.0000'), (33, 'NaN')):
            _, raw, _ = self.fixture(document_type=kind, amount=amount)
            with self.subTest(kind=kind, amount=amount), self.assertRaises(ted.TEDError):
                ted.parse_ted(raw)
        _, raw, _ = self.fixture(document_type=39)
        with self.assertRaisesRegex(ted.TEDError, '^ted-document-type-unsupported$'):
            ted.parse_ted(raw)

    def test_stored_caf_is_bound_byte_for_byte_without_rewriting(self):
        original, raw, _ = self.fixture(caf_pretty=True)
        compact = original.replace(b'\r\n\t ', b'')
        self.assertNotEqual(original, compact)
        self.assertTrue(ted.verify_ted(raw, {3: self.anchor}).caf_authority_verified)
        with self.assertRaisesRegex(ted.TEDError, '^ted-stored-caf-mismatch$'):
            ted.check_ted_against_caf(raw, compact)
        self.assertEqual(ted.check_ted_against_caf(raw, original).ted.original_bytes(), raw)

    def test_expected_context_compares_all_fields_and_rejects_float(self):
        _, raw, _ = self.fixture()
        context = ted.TEDContext('76086428-5', 33, 50, date(2026, 10, 1),
            '11111111-1', 'SYNTHETIC Peñón &  Hijos', Decimal('1234'), 'Cajón  Ñandú <Local>')
        self.assertTrue(ted.verify_ted(raw, {3: self.anchor}, expected=context).expected_context_matched)
        for change in ({'issuer_rut': '11111111-1'}, {'receiver_rut': '76086428-5'},
                       {'document_type': 34}, {'folio': 51}, {'emission_date': date(2026, 10, 2)},
                       {'receiver_name': 'other'}, {'first_item': 'other'}, {'total': Decimal('1234.0001')},
                       {'total': 1234.0}, {'total': Decimal('NaN')}, {'total': Decimal('sNaN')},
                       {'total': Decimal('Infinity')}, {'receiver_name': False},
                       {'folio': True}, {'emission_date': datetime(2026, 10, 1)}):
            with self.subTest(fields=list(change)), self.assertRaises(ted.TEDError):
                ted.verify_ted(raw, {3: self.anchor}, expected=replace(context, **change))

    def test_forged_receipts_and_untrusted_authorities_do_not_enable_verification(self):
        _, raw, _ = self.fixture()
        parsed = ted.parse_ted(raw)
        with self.assertRaisesRegex(ted.TEDError, '^ted-size-or-type$'):
            ted.verify_ted(parsed, {3: self.anchor})
        with self.assertRaisesRegex(ted.TEDError, '^ted-caf-authority-fingerprint-mismatch$'):
            ted.verify_ted(raw, {3: replace(self.anchor, fingerprint_sha256='0' * 64)})
        with self.assertRaisesRegex(ted.TEDError, '^ted-authority-map$'):
            ted.verify_ted(raw, None)
        self.assertFalse(ted.verify_ted(raw, {3: self.anchor}).metadata()['dte_xml_signature_verified'])
