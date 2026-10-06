from datetime import timedelta
import time
from unittest.mock import patch
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user
from ..models.whatsapp import PRIVATE
from ..provider import MockWhatsAppProvider, ProviderError, normalize, signature_valid, event_key


@tagged('post_install','-at_install')
class TestSupport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team=cls.env['helpdesk.team'].create({'name':'WA QA','company_id':cls.env.company.id,'use_sla':False})
        cls.channel=cls.env['step.helpdesk.wa.channel'].create({'name':'WA QA','team_id':cls.team.id,'enabled':True})

    def incoming(self, mid='msg-1', sender='56900000001', text='Necesito ayuda', reply=None):
        return {'kind':'incoming','external_id':mid,'sender':sender,'text':text,'type':'text','timestamp':str(int(time.time())),'reply_to':reply}

    def process(self, events):
        self.channel._ingest(events)
        for event in self.env['step.helpdesk.wa.event'].search([('state','=','pending'),('channel_id','=',self.channel.id)]):
            event._process();event.state='done'
        return self.env['step.helpdesk.wa.message'].search([('channel_id','=',self.channel.id)],order='id')

    def test_create_continue_and_duplicate(self):
        first=self.process([self.incoming()])
        self.assertEqual(len(first),1);self.assertTrue(first.ticket_id)
        self.process([self.incoming()])
        more=self.process([self.incoming('msg-2')])
        self.assertEqual(len(more),2);self.assertEqual(len(more.mapped('ticket_id')),1)
        self.assertEqual(first.mail_message_id.message_type,'email')
        self.assertTrue(first.mail_message_id.step_wa_inbound)

    def test_later_payload_does_not_create_duplicate(self):
        self.process([self.incoming()]);event=self.incoming(text='contenido cambiado')
        messages=self.process([event]);self.assertEqual(len(messages),1)

    def test_batch_all_senders(self):
        messages=self.process([self.incoming(),self.incoming('msg-2','56900000002')])
        self.assertEqual(len(messages),2);self.assertEqual(len(messages.mapped('ticket_id')),2)

    def test_closed_case_creates_linked_new_case(self):
        first=self.process([self.incoming()])
        stage=self.env['helpdesk.stage'].create({'name':'WA cerrado','fold':True})
        first.ticket_id.stage_id=stage
        more=self.process([self.incoming('msg-2')])
        self.assertNotEqual(more[-1].ticket_id,first.ticket_id)
        self.assertEqual(more[-1].ticket_id.step_wa_previous_ticket_id,first.ticket_id)

    def test_ambiguous_cases_wait_for_classification(self):
        first=self.process([self.incoming()]);c=first.conversation_id
        self.env['helpdesk.ticket'].create({'name':'Otro caso','team_id':self.team.id,'step_wa_conversation_id':c.id})
        messages=self.process([self.incoming('msg-2')]);self.assertFalse(messages[-1].ticket_id)
        choice=self.process([self.incoming('msg-3',text='caso #'+str(first.ticket_id.id))])
        self.assertEqual(choice[-1].ticket_id,first.ticket_id)

    def test_foreign_reference_does_not_attach(self):
        own=self.process([self.incoming()]);foreign=self.process([self.incoming('foreign','56900000002')])[-1]
        messages=self.process([self.incoming('msg-2',text='ticket #'+str(foreign.ticket_id.id))])
        message=messages.filtered(lambda m:m.external_id=='msg-2')
        self.assertFalse(message.ticket_id)
        reply=self.process([self.incoming('msg-3',reply=foreign.external_id)])
        self.assertEqual(reply[-1].ticket_id,own.ticket_id)

    def outgoing(self, incoming, **values):
        return self.env['step.helpdesk.wa.message'].with_context(_wa_private=PRIVATE).create(dict(
            channel_id=self.channel.id,conversation_id=incoming.conversation_id.id,ticket_id=incoming.ticket_id.id,
            direction='outgoing',kind='text',text='Respuesta de prueba',**values))

    def test_no_automatic_send_from_notes(self):
        incoming=self.process([self.incoming()]);incoming.ticket_id.message_post(body='Nota interna',subtype_xmlid='mail.mt_note')
        self.assertFalse(self.env['step.helpdesk.wa.message'].search([('direction','=','outgoing'),('channel_id','=',self.channel.id)]))

    def test_one_receipt_per_ticket(self):
        self.channel.auto_receipt=True
        self.process([self.incoming(),self.incoming('msg-2')])
        self.assertEqual(self.env['step.helpdesk.wa.message'].search_count([('direction','=','outgoing'),('channel_id','=',self.channel.id)]),1)

    def test_mock_never_requests_network(self):
        incoming=self.process([self.incoming()]);out=self.outgoing(incoming)
        with patch('requests.request',side_effect=AssertionError('No network')):
            out._send()
        self.assertEqual(out.state,'accepted');self.assertTrue(out.external_id.startswith('mock.'))

    def test_expired_while_pending_is_blocked(self):
        incoming=self.process([self.incoming()]);out=self.outgoing(incoming)
        incoming.conversation_id.last_incoming=fields.Datetime.now()-timedelta(hours=25)
        with patch.object(MockWhatsAppProvider,'send',side_effect=AssertionError('Must not send')):out._send()
        self.assertEqual(out.state,'failed')

    def test_approved_template_requires_consent_and_does_not_open_window(self):
        incoming=self.process([self.incoming()]);self.channel.action_sync_templates()
        template=self.env['step.helpdesk.wa.template'].search([('channel_id','=',self.channel.id)],limit=1)
        out=self.outgoing(incoming);out.write({'kind':'template','template_id':template.id})
        with self.assertRaises(UserError):out._check_send()
        incoming.conversation_id.write({'consent':True,'last_incoming':fields.Datetime.now()-timedelta(hours=25)})
        out._send();self.assertEqual(out.state,'accepted')
        self.assertFalse(out._window_open())

    def test_uncertain_is_not_resent(self):
        incoming=self.process([self.incoming()]);out=self.outgoing(incoming)
        with patch.object(MockWhatsAppProvider,'send',side_effect=ProviderError('timeout',uncertain=True)):out._send()
        self.assertEqual(out.state,'uncertain')
        with patch.object(MockWhatsAppProvider,'send',side_effect=AssertionError('No resend')):out._send()

    def test_retry_backoff(self):
        out=self.outgoing(self.process([self.incoming()]))
        with patch.object(MockWhatsAppProvider,'send',side_effect=ProviderError('429',retry=True)):out._send()
        self.assertEqual(out.state,'pending');self.assertGreater(out.next_attempt,fields.Datetime.now())

    def test_status_monotonic_and_no_ticket(self):
        out=self.outgoing(self.process([self.incoming()]));out._send()
        for status in ['read','sent','delivered','failed']:
            out._status({'status':status,'external_id':out.external_id})
        self.assertEqual(out.state,'read')
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('team_id','=',self.team.id)]),1)

    def test_media_failure_does_not_lose_ticket(self):
        event=self.incoming();event.update(type='document',media_id='fixture',mime='application/pdf')
        incoming=self.process([event])
        with patch.object(MockWhatsAppProvider,'download',side_effect=ProviderError('offline',retry=True)):incoming._fetch_media()
        self.assertTrue(incoming.ticket_id);self.assertEqual(incoming.media_state,'pending')
        incoming._fetch_media();self.assertEqual(incoming.media_state,'done')
        self.assertFalse(incoming.attachment_id.public)

    def test_audio_saved_without_transcription(self):
        event=self.incoming();event.update(type='audio',text='',media_id='audio',mime='audio/ogg')
        incoming=self.process([event]);incoming._fetch_media()
        self.assertEqual(incoming.attachment_id.mimetype,'audio/ogg');self.assertFalse(incoming.text)

    def test_incomplete_channel_cannot_activate(self):
        c=self.env['step.helpdesk.wa.channel'].create({'name':'Sin secretos','team_id':self.team.id,'provider':'meta_cloud'})
        with self.assertRaises(ValidationError),self.env.cr.savepoint():c.enabled=True

    def test_old_channel_mapping_is_immutable(self):
        self.process([self.incoming()])
        with self.assertRaises(UserError):self.channel.provider='meta_cloud'

    def test_cross_company_and_private_team(self):
        incoming=self.process([self.incoming()])
        other_company=self.env['res.company'].create({'name':'WA Otra'})
        other=new_test_user(self.env,login='wa.other',groups='helpdesk.group_helpdesk_user',company_id=other_company.id,company_ids=[(6,0,[other_company.id])])
        self.assertFalse(self.env['step.helpdesk.wa.message'].with_user(other).search([('id','=',incoming.id)]))
        same=new_test_user(self.env,login='wa.private',groups='helpdesk.group_helpdesk_user',company_id=self.env.company.id)
        self.team.privacy_visibility='invited_internal'
        with self.assertRaises(AccessError):incoming.with_user(same).read(['text'])
        self.team.write({'member_ids':[(4,same.id)]})
        self.assertTrue(incoming.with_user(same).read(['text']))
        with self.assertRaises(AccessError):incoming.conversation_id.with_user(same).write({'last_incoming':fields.Datetime.now()})
        with self.assertRaises(AccessError):self.channel.with_user(same).read(['access_token'])

    def test_no_rpc_can_create_fake_incoming_or_approval(self):
        with self.assertRaises(AccessError):self.env['step.helpdesk.wa.message'].create({'text':'Fake'})
        with self.assertRaises(AccessError):self.env['step.helpdesk.wa.template'].create({'channel_id':self.channel.id,'name':'fake','approved':True})
        with self.assertRaises(AccessError):self.env['mail.message'].create({'body':'fake','step_wa_inbound':True})

    def test_multimessage_normalization_and_scope(self):
        payload={'entry':[{'id':'a','changes':[{'field':'messages','value':{'metadata':{'phone_number_id':'p'},'messages':[
            {'id':'1','from':'s','type':'text','text':{'body':'a'}},{'id':'2','from':'t','type':'text','text':{'body':'b'}}],
            'statuses':[{'id':'3','status':'read'}]}}]}]}
        self.assertEqual(len(normalize(payload,'a','p')),3)
        with self.assertRaises(ValueError):normalize(payload,'wrong','p')
        with self.assertRaises(ValueError):normalize(payload,'a','wrong')
        self.assertFalse(signature_valid(b'{}','sha256='+'0'*64,'secret'))
        self.assertEqual(event_key(self.incoming()),event_key(self.incoming(text='later')))
