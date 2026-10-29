"""Published manual transcriptions and explicit synthetic hostile responses.

No fixture is a live SII response or an operational CAF/certificate/master.
"""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from .. import upload_response as api


FIXTURES = Path(__file__).with_name('fixtures')


class UploadResponseCases:
    def source(self, name='success'):
        return (FIXTURES / ('upload_manual_' + name + '.xml')).read_bytes()

    def response(self, name='success'):
        return api.parse_upload_response(self.source(name))

    def assertRejected(self, payload, code=None):
        with self.assertRaises(api.UploadResponseError) as caught:
            api.parse_upload_response(payload)
        if code:
            self.assertEqual(str(caught.exception), code)

    def test_public_success_is_receipt_not_dte_acceptance(self):
        response = self.response()
        self.assertEqual((response.sender_rut,response.company_rut,response.track_id),('1-9','3-5','39'))
        self.assertEqual(response.received_local_time,datetime(2002,11,25,18,51,44))
        self.assertTrue(response.reports_received)
        self.assertIsNone(response.dte_acceptance)
        self.assertFalse(response.source_authentication_verified)
        self.assertEqual(response.original_bytes(),self.source())

    def test_public_failure_has_no_track_and_no_inferred_retry_policy(self):
        response=self.response('failure')
        self.assertEqual(response.status,5)
        self.assertIsNone(response.track_id)
        self.assertFalse(response.reports_received)
        with self.assertRaisesRegex(api.UploadResponseError,'upload-not-received'):
            api.admit_upload_receipt(response,sender_rut='1-9',company_rut='3-5',filename=response.filename)

    def test_public_schema_failure_retains_details_and_zero_padded_rut(self):
        response=self.response('schema_failure')
        self.assertEqual(response.sender_rut,'7880442-4')
        self.assertEqual((response.status,len(response.errors)),(7,2))
        self.assertIn('LSX-00265',response.errors[0])
        self.assertIn(b'07880442-4',response.original_bytes())

    def test_published_fixture_provenance_and_hashes(self):
        manifest=json.loads((FIXTURES/'upload_manual_provenance.json').read_text())
        self.assertEqual(manifest['source_pdf_sha256'],'875792e9e2926f363614edade4271055a4c39cd88730c86e2a9e02b630e75b2d')
        for name,entry in manifest['fixtures'].items():
            self.assertEqual(hashlib.sha256((FIXTURES/name).read_bytes()).hexdigest(),entry['sha256'])
            self.assertFalse(entry['live_sii_response'])

    def test_both_encodings_accents_entities_and_original_bytes(self):
        text=self.source('schema_failure').decode().replace('ENVFIN_100_sign.xml','Ñandú &amp; Cía.xml')
        for encoding in ('UTF-8','ISO-8859-1'):
            payload=('<?xml version="1.0" encoding="'+encoding+'"?>'+text).encode(encoding)
            response=api.parse_upload_response(payload)
            self.assertEqual(response.filename,'Ñandú & Cía.xml')
            self.assertEqual(response.original_bytes(),payload)

    def test_rut_format_check_digit_and_zero_identity_rejected(self):
        for value in (b'1-0',b'0-0',b'000-0',b'1234567890-K',b'',b'1- 9'):
            self.assertRejected(self.source().replace(b'1-9',value))

    def test_track_numeric_positive_bound_and_literal_identity(self):
        for value in (b'0',b'-1',b'track',b'1'*33,b''):
            self.assertRejected(self.source().replace(b'>39<',b'>'+value+b'<'),'track-id-format')
        response=api.parse_upload_response(self.source().replace(b'>39<',b'>00039<'))
        self.assertEqual(response.track_id,'00039')

    def test_status_and_track_consistency(self):
        self.assertRejected(self.source().replace(b'<TRACKID>39</TRACKID>',b''),'status-track-inconsistent')
        self.assertRejected(self.source().replace(b'<STATUS>0</STATUS>',b'<STATUS>5</STATUS>'),'status-track-inconsistent')
        self.assertRejected(self.source().replace(b'</RECEPCIONDTE>',b'<DETAIL><ERROR>synthetic</ERROR></DETAIL></RECEPCIONDTE>'),'status-track-inconsistent')

    def test_status_format_and_unknown_failure_are_not_success(self):
        for value in (b'-1',b'0.0',b'OK',b'1000',b''):
            self.assertRejected(self.source('failure').replace(b'>5<',b'>'+value+b'<'),'status-format')
        response=api.parse_upload_response(self.source('failure').replace(b'>5<',b'>999<'))
        self.assertEqual(response.status,999)
        self.assertFalse(response.reports_received)

    def test_duplicate_unknown_wrapped_and_mixed_root_fields_rejected(self):
        payload=self.source()
        for bad in (payload.replace(b'<STATUS>0</STATUS>',b'<STATUS>0</STATUS><STATUS>0</STATUS>'),
                    payload.replace(b'</RECEPCIONDTE>',b'<TOKEN>not-a-token</TOKEN></RECEPCIONDTE>'),
                    b'<WRAPPER>'+payload.split(b'?>')[1]+b'</WRAPPER>',
                    payload.replace(b'<FILE>',b'SYNTHETIC<FILE>')):
            self.assertRejected(bad)

    def test_namespace_and_root_attributes_are_not_alternate_formats(self):
        for opening in (b'<RECEPCIONDTE xmlns="http://www.sii.cl/SiiDte">',
                        b'<RECEPCIONDTE xmlns:x="urn:unknown">',b'<RECEPCIONDTE status="0">'):
            self.assertRejected(self.source().replace(b'<RECEPCIONDTE>',opening))
        self.assertRejected(self.source().replace(b'RECEPCIONDTE',b'RespuestaEnvioDTE'))

    def test_dtd_external_and_internal_entities_are_never_expanded(self):
        body=self.source().split(b'?>')[1]
        for doctype in (b'<!DOCTYPE RECEPCIONDTE SYSTEM "https://example.invalid/never-request">',
                        b'<!DOCTYPE RECEPCIONDTE [<!ENTITY x SYSTEM "file:///never-open">]>',
                        b'<!DOCTYPE RECEPCIONDTE [<!ENTITY x "synthetic-secret">]>'):
            self.assertRejected(doctype+body)

    def test_comments_and_processing_instructions_are_rejected(self):
        for bad in (b'<!--extra-->'+self.source().split(b'?>')[1],
                    self.source()+b'<!--extra-->',
                    self.source().replace(b'<STATUS>',b'<?test data?><STATUS>'),
                    self.source().replace(b'<STATUS>',b'<!--inside--><STATUS>')):
            self.assertRejected(bad,'response-extra-node')

    def test_scalar_nested_markup_attributes_and_detail_shape_rejected(self):
        for bad in (self.source().replace(b'>39<',b'><value>39</value><'),
                    self.source().replace(b'<TRACKID>',b'<TRACKID value="39">'),
                    self.source('schema_failure').replace(b'<ERROR>',b'<OTHER>'),
                    self.source('schema_failure').replace(b'<DETAIL>',b'<DETAIL>mixed'),
                    self.source('schema_failure').replace(b'<DETAIL>',b'<DETAIL flag="x">')):
            self.assertRejected(bad)

    def test_xml_type_size_encoding_and_malformed_input_rejected(self):
        for payload in (self.source().decode(),None,b'',b'x'*(api.MAX_RESPONSE_BYTES+1),self.source()+b'<other/>'):
            self.assertRejected(payload)
        self.assertRejected(self.source().decode().encode('utf-16'),'response-encoding')
        self.assertRejected(self.source().replace(b'version="1.0"',b'version="1.1"'),'response-xml-version')
        self.assertEqual(api.parse_upload_response(b'\xef\xbb\xbf'+self.source()).track_id,'39')

    def test_local_timestamp_is_validated_without_timezone_assumption(self):
        self.assertIsNone(self.response().received_local_time.tzinfo)
        for value in (b'2002-02-30 18:51:44',b'2002-11-25T18:51:44Z',b'2002-11-25 25:00:00'):
            self.assertRejected(self.source().replace(b'2002-11-25 18:51:44',value),'timestamp-format')

    def test_context_admission_keeps_existing_identifier(self):
        response=self.response()
        admitted=api.admit_upload_receipt(response,sender_rut='0001-9',company_rut='3-5',
            filename='EnvioEjemplo.xml',existing_track_id='39')
        self.assertEqual(admitted,response)
        self.assertEqual(admitted.track_id,'39')
        self.assertFalse(admitted.source_authentication_verified)

    def test_context_mismatch_and_existing_track_cannot_be_overwritten(self):
        defaults=dict(sender_rut='1-9',company_rut='3-5',filename='EnvioEjemplo.xml',existing_track_id='39')
        for key,value in (('sender_rut','3-5'),('company_rut','1-9'),('filename','other.xml'),('existing_track_id','40')):
            context=dict(defaults,**{key:value})
            with self.assertRaises(api.UploadResponseError):api.admit_upload_receipt(self.response(),**context)
        with self.assertRaisesRegex(api.UploadResponseError,'existing-track-conflict'):
            api.admit_upload_receipt(self.response('failure'),**defaults)

    def test_forged_or_mutated_dataclass_cannot_bypass_reparse(self):
        response=self.response()
        for forged in (replace(response,track_id='40'),replace(response,status=5),replace(response,response_sha256='0'*64)):
            with self.assertRaisesRegex(api.UploadResponseError,'response-receipt-mismatch'):
                api.admit_upload_receipt(forged,sender_rut='1-9',company_rut='3-5',filename='EnvioEjemplo.xml')
        with self.assertRaises(FrozenInstanceError):response.status=5

    def test_representations_and_errors_never_echo_remote_content(self):
        secret='SYNTHETIC_PRIVATE_MESSAGE_DO_NOT_ECHO'
        payload=self.source('schema_failure').replace(b'ENVFIN_100_sign.xml',secret.encode()).replace(b'LSX-00265',secret.encode())
        response=api.parse_upload_response(payload)
        self.assertNotIn(secret,repr(response))
        with self.assertRaises(api.UploadResponseError)as caught:
            api.admit_upload_receipt(response,sender_rut='1-9',company_rut='3-5',filename=secret)
        self.assertNotIn(secret,str(caught.exception))

    def test_no_network_or_state_changes_for_parsing_and_admission(self):
        payload=self.source();before=bytes(payload)
        with patch('socket.socket',side_effect=AssertionError('Network is forbidden')):
            response=api.parse_upload_response(payload)
            api.admit_upload_receipt(response,sender_rut='1-9',company_rut='3-5',filename='EnvioEjemplo.xml')
        self.assertEqual(payload,before)
        self.assertEqual(response.original_bytes(),before)

    def test_error_detail_bounds_and_field_order(self):
        body=self.source('failure').replace(b'</RECEPCIONDTE>',b'<DETAIL>'+b'<ERROR>synthetic</ERROR>'*(api.MAX_DETAIL_ERRORS+1)+b'</DETAIL></RECEPCIONDTE>')
        self.assertRejected(body,'detail-format')
        payload=self.source().replace(b'  <STATUS>0</STATUS>\n',b'').replace(b'</RECEPCIONDTE>',b'<STATUS>0</STATUS></RECEPCIONDTE>')
        self.assertEqual(api.parse_upload_response(payload).track_id,'39')
