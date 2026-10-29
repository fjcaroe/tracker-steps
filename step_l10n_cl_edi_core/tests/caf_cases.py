"""Generated, deliberately non-SII CAFs. No business data or real secrets."""
import base64
from dataclasses import replace
from datetime import date, datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .. import caf


def _number(value):
    return base64.b64encode(value.to_bytes((value.bit_length() + 7) // 8, 'big')).decode()


class CAFCaseMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        pem = cls.signer.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.anchor = caf.TrustAnchor(3, caf.public_key_fingerprint(cls.signer.public_key()), pem)

    def fixture(self, *, pretty=False, namespace=False, private=False,
                name='Prueba Ñandú &amp; Hijos  Ltda.', first=50, last=101,
                encoding='ISO-8859-1'):
        numbers = self.issuer_key.public_key().public_numbers()
        # Independently defined literal signature payload. The verifier never
        # supplies this payload to the fixture signer.
        payload = ('<DA><RE>76086428-5</RE><RS>' + name + '</RS><TD>33</TD>'
                   '<RNG><D>' + str(first) + '</D><H>' + str(last) + '</H></RNG>'
                   '<FA>2026-10-01</FA><RSAPK><M>' + _number(numbers.n)
                   + '</M><E>' + _number(numbers.e) + '</E></RSAPK><IDK>3</IDK></DA>')
        signature = self.signer.sign(payload.encode('iso-8859-1'),
                                     padding.PKCS1v15(), hashes.SHA1())
        data = payload.replace('><', '>\r\n\t <') if pretty else payload
        if namespace:
            data = data.replace('<DA>', '<DA xmlns="http://www.sii.cl/SiiDte">')
        xml = '<CAF version="1.0">' + data + '<FRMA algoritmo="SHA1withRSA">'
        xml += base64.b64encode(signature).decode() + '</FRMA></CAF>'
        if private:
            secret = self.issuer_key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
            public = self.issuer_key.public_key().public_bytes(serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo).decode()
            xml = '<AUTORIZACION>' + xml + '<RSASK>' + secret + '</RSASK><RSAPUBK>' + public + '</RSAPUBK></AUTORIZACION>'
        if namespace:
            xml = xml.replace('<CAF version=', '<CAF xmlns="http://www.sii.cl/SiiDte" version=')
            xml = xml.replace('<AUTORIZACION>', '<AUTORIZACION xmlns="http://www.sii.cl/SiiDte">')
        return ('<?xml version="1.0" encoding="' + encoding + '"?>\r\n' + xml).encode(encoding)

    def verified(self, **options):
        return caf.verify_caf(caf.parse_caf(self.fixture(**options)), {3: self.anchor})

    def assert_code(self, code, callback):
        with self.assertRaisesRegex(caf.CAFError, '^' + code + '$'):
            callback()

    def context(self, **overrides):
        result = dict(issuer_rut='76.086.428-5', document_type=33, folio=50,
                      emission_date=date(2026, 10, 1))
        result.update(overrides)
        return result

    def test_real_rsa_verification_and_metadata(self):
        verified = self.verified()
        parsed = verified.caf
        self.assertEqual((parsed.issuer_rut, parsed.document_type, parsed.folio_from,
                          parsed.folio_to, parsed.authorization_date, parsed.authority_key_id),
                         ('76086428-5', 33, 50, 101, date(2026, 10, 1), 3))
        self.assertFalse(parsed.has_private_key)

    def test_latin1_accent_entities_and_internal_spaces_are_signed(self):
        for options in ({}, {'pretty': True}, {'namespace': True},
                        {'pretty': True, 'namespace': True}, {'encoding': 'UTF-8'}):
            with self.subTest(options=options):
                parsed = self.verified(**options).caf
                self.assertIn('Ñandú &amp; Hijos  Ltda.'.encode('latin1'), parsed._signed_data)
                self.assertNotIn(b'xmlns', parsed._signed_data)
                self.assertNotIn(b'\r', parsed._signed_data)

    def test_complete_authorization_preserved_byte_for_byte(self):
        original = self.fixture(private=True, pretty=True)
        parsed = caf.parse_caf(original)
        self.assertEqual(parsed.original_bytes(), original)
        self.assertTrue(parsed.verify_key_pair())
        self.assertTrue(parsed.has_private_key)
        self.assertNotIn('PRIVATE KEY', repr(parsed))
        self.assertNotIn('Prueba', repr(parsed))
        self.assertNotIn(b'RSASK', parsed.public_caf_bytes())
        caf.verify_caf(parsed, {3: self.anchor})

    def test_private_key_mismatch_and_invalid_key_rejected_without_echo(self):
        original = self.fixture(private=True)
        parsed = caf.parse_caf(original)
        foreign = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        secret = foreign.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
        self.assert_code('authorization-key-mismatch', lambda:
                         replace(parsed, _private_pem=secret).verify_key_pair())
        self.assert_code('authorization-key-format', lambda:
                         replace(parsed, _private_pem=b'private sensitive bad input').verify_key_pair())
        self.assert_code('private-key-absent', lambda: self.verified().caf.verify_key_pair())

    def test_missing_authority_never_trusts_caf_public_key(self):
        parsed = caf.parse_caf(self.fixture())
        self.assert_code('authority-untrusted', lambda: caf.verify_caf(parsed, {}))
        pem = self.issuer_key.public_key().public_bytes(serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo)
        wrong = caf.TrustAnchor(3, caf.public_key_fingerprint(self.issuer_key.public_key()), pem)
        self.assert_code('signature-invalid', lambda: caf.verify_caf(parsed, {3: wrong}))

    def test_pinned_fingerprint_and_id_required(self):
        parsed = caf.parse_caf(self.fixture())
        self.assert_code('authority-fingerprint-mismatch', lambda:
            caf.verify_caf(parsed, {3: replace(self.anchor, fingerprint_sha256='0' * 64)}))
        self.assert_code('authority-untrusted', lambda:
            caf.verify_caf(parsed, {3: replace(self.anchor, key_id=4)}))
        self.assert_code('authority-key-format', lambda:
            caf.verify_caf(parsed, {3: replace(self.anchor, public_key_pem=b'no key')}))

    def test_changed_signed_values_fail(self):
        original = self.fixture()
        for old, new in ((b'<H>101</H>', b'<H>102</H>'),
                         (b'<TD>33</TD>', b'<TD>34</TD>'),
                         (b'Hijos  Ltda.', b'Hijos Ltda.')):
            with self.subTest(old=old):
                self.assert_code('signature-invalid', lambda:
                    caf.verify_caf(caf.parse_caf(original.replace(old, new)), {3: self.anchor}))

    def test_signature_bytes_and_algorithm_fail_closed(self):
        original = self.fixture()
        parsed = caf.parse_caf(original)
        self.assert_code('signature-invalid', lambda:
            caf.verify_caf(caf.parse_caf(original.replace(
                base64.b64encode(parsed._signature), base64.b64encode(b'bad signature'))),
                {3: self.anchor}))
        self.assert_code('signature-algorithm', lambda:
            caf.parse_caf(original.replace(b'SHA1withRSA', b'SHA256withRSA')))
        self.assert_code('signature-base64', lambda:
            caf.parse_caf(original.replace(b'</FRMA>', b'*</FRMA>')))

    def test_dtd_entities_comments_and_processing_instructions_rejected(self):
        original = self.fixture()
        attacks = (b'<!DOCTYPE CAF [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>',
                   b'<!-- hidden CAF -->', b'<?unsafe anything?>')
        for attack in attacks:
            with self.subTest(attack=attack):
                self.assertRaises(caf.CAFError, caf.parse_caf,
                    original.replace(b'<CAF version=', attack + b'<CAF version='))

    def test_duplicate_wrapped_and_unknown_elements_rejected(self):
        original = self.fixture()
        variants = (original.replace(b'<TD>33</TD>', b'<TD>33</TD><TD>34</TD>'),
                    original.replace(b'</DA>', b'<EXTRA>1</EXTRA></DA>'),
                    original.replace(b'<RSAPK>', b'<RSAPK injected="1">'),
                    original.replace(b'<RE>', b'<RE><wrapper>'),
                    original.replace(b'</RE>', b'</wrapper></RE>'))
        for variant in variants:
            with self.subTest(variant_length=len(variant)):
                self.assertRaises(caf.CAFError, caf.parse_caf, variant)
        fragment = original.split(b'\r\n', 1)[1]
        self.assert_code('xml-root', lambda: caf.parse_caf(
            b'<?xml version="1.0" encoding="ISO-8859-1"?><wrapper>' + fragment + b'</wrapper>'))
        self.assertRaises(caf.CAFError, caf.parse_caf, b'<AUTORIZACION>' + fragment + fragment + b'</AUTORIZACION>')

    def test_foreign_and_prefixed_namespaces_rejected(self):
        original = self.fixture(namespace=True)
        self.assert_code('xml-namespace', lambda:
            caf.parse_caf(original.replace(b'http://www.sii.cl/SiiDte', b'https://attacker.invalid')))
        self.assertRaises(caf.CAFError, caf.parse_caf,
            self.fixture().replace(b'<DA>', b'<DA xmlns="urn:foreign">'))
        self.assertRaises(caf.CAFError, caf.parse_caf,
            self.fixture().replace(b'<CAF ', b'<p:CAF xmlns:p="http://www.sii.cl/SiiDte" ').replace(b'</CAF>', b'</p:CAF>'))

    def test_invalid_values_ranges_dates_and_issuer_rejected(self):
        original = self.fixture()
        replacements = ((b'76086428-5', b'76086428-6'), (b'<D>50</D>', b'<D>102</D>'),
                        (b'<H>101</H>', b'<H>0</H>'), (b'<TD>33</TD>', b'<TD>+33</TD>'),
                        (b'2026-10-01', b'2026-02-30'), (b'<IDK>3</IDK>', b'<IDK>0</IDK>'))
        for old, new in replacements:
            with self.subTest(old=old):
                self.assertRaises(caf.CAFError, caf.parse_caf, original.replace(old, new))

    def test_size_type_encoding_and_unicode_bounds(self):
        for value in (b'', 'not bytes', b' ' * (caf.MAX_XML_BYTES + 1)):
            self.assert_code('xml-size-or-type', lambda: caf.parse_caf(value))
        self.assert_code('xml-encoding', lambda: caf.parse_caf(self.fixture().decode('latin1').replace('ISO-8859-1', 'UTF-16').encode('utf-16')))
        self.assert_code('data-not-latin1', lambda:
            caf.parse_caf(self.fixture(encoding='UTF-8').replace(b'Prueba', '\u03a9'.encode())))

    def test_boundaries_and_date_check_without_counter_mutation(self):
        verified = self.verified(private=True)
        before = verified.caf.original_bytes()
        for folio in (50, 101, 50):
            self.assertIs(caf.validate_folio(verified, **self.context(folio=folio)), verified.caf)
        self.assertEqual(verified.caf.original_bytes(), before)
        for folio in (49, 102, True, '50'):
            self.assert_code('folio-outside-range', lambda:
                caf.validate_folio(verified, **self.context(folio=folio)))
        self.assert_code('emission-before-authorization', lambda:
            caf.validate_folio(verified, **self.context(emission_date=date(2026, 9, 30))))
        self.assert_code('emission-date-format', lambda:
            caf.validate_folio(verified, **self.context(emission_date=datetime(2026, 10, 1))))

    def test_context_and_unverified_receipts_rejected(self):
        verified = self.verified()
        self.assert_code('caf-unverified', lambda:
            caf.validate_folio(verified.caf, **self.context()))
        self.assert_code('issuer-mismatch', lambda:
            caf.validate_folio(verified, **self.context(issuer_rut='11111111-1')))
        self.assert_code('document-type-mismatch', lambda:
            caf.validate_folio(verified, **self.context(document_type=34)))
        changed = replace(verified, caf=replace(verified.caf, folio_to=1000))
        self.assert_code('caf-receipt-mismatch', lambda:
            caf.validate_folio(changed, **self.context(folio=999)))

    def test_unique_selection_overlap_and_no_match(self):
        first = self.verified()
        second = self.verified(first=102, last=200)
        self.assertEqual(caf.select_caf([first, second], **self.context(folio=101)), first.caf)
        self.assertEqual(caf.select_caf([first, second], **self.context(folio=102)), second.caf)
        self.assert_code('folio-no-caf', lambda:
            caf.select_caf([first, second], **self.context(folio=201)))
        self.assert_code('folio-ambiguous', lambda:
            caf.select_caf([first, first], **self.context()))
        self.assert_code('folio-ambiguous', lambda:
            caf.select_caf([first, self.verified(first=75, last=110)], **self.context(folio=75)))

    def test_selection_does_not_hide_invalid_signatures(self):
        verified = self.verified()
        corrupted = replace(verified, caf=caf.parse_caf(
            verified.caf.original_bytes().replace(b'<H>101</H>', b'<H>102</H>')))
        self.assert_code('signature-invalid', lambda:
            caf.select_caf([verified, corrupted], **self.context()))
