import hashlib
import hmac
import json
from odoo.tests import HttpCase, tagged


@tagged('post_install','-at_install')
class TestWebhook(HttpCase):
    def setUp(self):
        super().setUp()
        team=self.env['helpdesk.team'].create({'name':'Webhook QA','company_id':self.env.company.id,'use_sla':False})
        self.channel=self.env['step.helpdesk.wa.channel'].create({'name':'Signed QA','team_id':team.id,
            'provider':'meta_cloud','enabled':True,'graph_version':'v26.0','app_id':'fixture_app','account_id':'fixture_account',
            'phone_number_id':'fixture_phone','access_token':'fixture_token','app_secret':'fixture_secret','verify_token':'fixture_verify'})

    def test_challenge_and_signature(self):
        path='/whatsapp/webhook/'+self.channel.route_key
        self.assertEqual(self.url_open(path+'?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=123').status_code,403)
        valid=self.url_open(path+'?hub.mode=subscribe&hub.verify_token=fixture_verify&hub.challenge=123')
        self.assertEqual(valid.status_code,200);self.assertEqual(valid.text,'123')
        data=json.dumps({'entry':[{'id':'fixture_account','changes':[{'field':'messages','value':{
            'metadata':{'phone_number_id':'fixture_phone'},'messages':[{'id':'fixture_msg','from':'56900000001','timestamp':'100','type':'text','text':{'body':'fixture'}}]}}]}]}).encode()
        headers={'Content-Type':'application/json'}
        invalid=self.url_open(path,data=data,headers=headers);self.assertEqual(invalid.status_code,403)
        headers['X-Hub-Signature-256']='sha256='+hmac.new(b'fixture_secret',data,hashlib.sha256).hexdigest()
        self.assertEqual(self.url_open(path,data=data,headers=headers).status_code,200)
        self.assertEqual(self.url_open(path,data=data,headers=headers).status_code,200)
        self.assertEqual(self.env['step.helpdesk.wa.event'].search_count([('channel_id','=',self.channel.id)]),1)
        self.assertFalse(self.env['step.helpdesk.wa.message'].search([('channel_id','=',self.channel.id)]))
