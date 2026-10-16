import base64
from datetime import date, timedelta
from unittest.mock import Mock, patch
from odoo import fields, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_export_control.models.voyage import route_position


@tagged('post_install','-at_install')
class ExportControlCase(TransactionCase):
    def shipment(self,**values):
        self.env.company.export_folio_mode='document'
        return self.env['step.export.export'].with_context(tracking_disable=True,mail_create_nosubscribe=True).create({
            'name':'QA Paneles exportación','company_id':self.env.company.id,
            'departure_date':'2026-10-13','arrival_date':'2026-11-02',**values})

    def test_document_deadlines_manual_and_legacy_preservation(self):
        shipment=self.shipment()
        self.assertEqual(len(shipment.documentation_ids),12)
        original=shipment.documentation_ids.ids
        shipment.action_complete_document_control()
        self.assertEqual(shipment.documentation_ids.ids,original)
        pf=shipment.documentation_ids.filtered(lambda l:l.kind=='pf')
        self.assertEqual(pf.customer_deadline,date(2026,10,10))
        self.assertEqual(pf.with_context(control_date='2026-10-09').control_color,'ontime')
        self.assertEqual(pf.with_context(control_date='2026-10-10').control_color,'today')
        self.assertEqual(pf.with_context(control_date='2026-10-11').control_color,'late')
        with self.assertRaises(ValidationError),self.cr.savepoint():
            pf.sent_on='2026-10-09'
        pf.write({'sent_on':'2026-10-09','manual_reference':'QA respaldo externo'})
        self.assertEqual(pf.with_context(control_date='2026-10-20').control_color,'ontime')
        self.assertEqual(pf.control_status,'sent')
        bl=shipment.documentation_ids.filtered(lambda l:l.kind=='bl')
        self.assertEqual(bl.customs_deadline,date(2026,10,14))
        legacy=shipment.documentation_ids.filtered(lambda l:l.kind=='dus')
        legacy.write({'status':'sent','date':'2026-10-15','originals':5,'copies':2})
        self.assertEqual(legacy.effective_sent_on,date(2026,10,15))
        shipment.action_complete_document_control()
        self.assertEqual((legacy.originals,legacy.copies),(5,2))
        data=self.env['step.export.export'].control_dashboard(query=shipment.shipment_number,consultation_date='2026-10-16')
        row=next(r for r in data['rows'] if r['id']==shipment.id)
        self.assertEqual(len(row['documents']),12)
        self.assertTrue(next(d for d in row['documents'] if d['kind']=='pf')['sent'])

    def test_only_successful_attached_email_marks_delivery(self):
        shipment=self.shipment()
        parameter=self.env.ref('step_export_control.type_ie')
        attachment=self.env['ir.attachment'].create({'name':'QA instruction.pdf','datas':base64.b64encode(b'QA document'),
            'res_model':shipment._name,'res_id':shipment.id,'mimetype':'application/pdf'})
        vals={'subject':'QA documents','model':shipment._name,'res_id':shipment.id,
            'email_from':'qa-sender@example.invalid','email_to':'qa-recipient@example.invalid',
            'attachment_ids':[Command.set(attachment.ids)],'export_control_type_ids':[Command.set(parameter.ids)],'auto_delete':True}
        mail=self.env['mail.mail'].create(vals)
        line=shipment.documentation_ids.filtered(lambda l:l.kind=='ie')
        self.assertFalse(line.sent_on)
        mail._postprocess_sent_message([],failure_type='smtp',failure_reason='QA failure')
        self.assertFalse(line.sent_on)
        server=type(self.env['ir.mail_server'])
        with patch.object(server,'connect',return_value=Mock()),patch.object(server,'send_email',return_value='<qa-delivered@example.invalid>'):
            mail.send(raise_exception=True)
        self.assertEqual(line.sent_on,fields.Date.context_today(line))
        self.assertTrue(line.sent_message_id)
        self.assertEqual(line.sent_attachment_ids,attachment)
        self.assertEqual(mail.state,'sent')
        self.assertFalse(mail.auto_delete)
        self.assertTrue(line.document_created_on)
        partner=self.env['res.partner'].create({'name':'QA destinatario','email':'qa-recipient@example.invalid'})
        composer=self.env['mail.compose.message'].create({'model':shipment._name,'res_ids':str(shipment.ids),
            'composition_mode':'comment','subject':'QA compositor','body':'QA documentos',
            'partner_ids':[Command.set(partner.ids)],'attachment_ids':[Command.set(attachment.ids)],
            'export_control_type_ids':[Command.set(parameter.ids)]})
        prepared=composer._prepare_mail_values(shipment.ids)[shipment.id]
        self.assertEqual(prepared['export_control_type_ids'],[Command.set(parameter.ids)])

    def test_voyage_dates_alert_boundaries_and_routes(self):
        shipment=self.shipment()
        self.assertEqual(shipment.transit_time,20)
        s=shipment._voyage_control_values(date(2026,10,12))
        self.assertEqual(s['voyage_status'],'scheduled')
        s=shipment._voyage_control_values(date(2026,10,26))
        self.assertEqual((s['voyage_status'],s['days_to_arrival'],s['near_arrival']),('transit',7,False))
        self.assertTrue(shipment._voyage_control_values(date(2026,10,27))['near_arrival'])
        s=shipment._voyage_control_values(date(2026,11,2))
        self.assertEqual((s['voyage_status'],s['days_to_arrival'],s['days_arrived']),('arrived',0,0))
        self.assertEqual(shipment._voyage_control_values(date(2026,11,5))['days_arrived'],3)
        shipment.transit_time=22
        self.assertEqual(shipment.arrival_date,date(2026,11,4))
        country=self.env.ref('base.cl')
        ports=self.env['l10n_cl.customs_port'].create([
            {'name':'QA origen','code':99001,'country_id':country.id,'control_coordinates_set':True,'control_latitude':-33,'control_longitude':-72},
            {'name':'QA destino','code':99002,'country_id':country.id,'control_coordinates_set':True,'control_latitude':34,'control_longitude':-118}])
        route=self.env['step.export.sea.route'].create({'name':'QA ruta','origin_port_id':ports[0].id,'destination_port_id':ports[1].id,
            'waypoint_ids':[Command.create({'name':'QA costa Pacífico','latitude':0,'longitude':-90})]})
        shipment.write({'origin_port_id':ports[0].id,'destination_port_id':ports[1].id,'sea_route_id':route.id})
        self.assertEqual(len(shipment._voyage_control_values(date(2026,10,16))['route']),3)
        self.assertTrue(shipment._voyage_control_values(date(2026,10,16))['theoretical_position'])
        self.assertFalse(shipment._voyage_control_values(date(2026,11,5))['theoretical_position'])
        self.assertAlmostEqual(abs(route_position([[0,179],[0,-179]],0.5)[1]),180)
        with self.assertRaises(ValidationError),self.cr.savepoint():
            shipment.destination_port_id=ports[0]

    def test_ais_validation_identity_age_and_company_access(self):
        vessel=self.env['step.export.vessel'].create({'name':'QA AIS','mmsi':'999000089','company_id':self.env.company.id})
        shipment=self.shipment(vessel_id=vessel.id)
        now=(fields.Datetime.now()-timedelta(minutes=1)).replace(microsecond=0)
        event={'MessageType':'PositionReport','MetaData':{'MMSI':999000089,'time_utc':str(now)+'.123456789 +0000 UTC'},
            'Message':{'PositionReport':{'Latitude':-20,'Longitude':-80,'Valid':True,'Sog':12,'Cog':22}}}
        vessel._ingest_ais_event(event)
        self.assertEqual(vessel.ais_latitude,-20)
        self.assertTrue(shipment._voyage_control_values(date(2026,10,16))['ais_fresh'])
        event['MetaData']['time_utc']=str(now-timedelta(days=1))+'+00:00'
        event['Message']['PositionReport']['Latitude']=-21
        vessel._ingest_ais_event(event)
        self.assertEqual(vessel.ais_latitude,-20)
        event['MetaData']['time_utc']=str(now+timedelta(seconds=1))+'+00:00'
        event['Message']['PositionReport']['Latitude']=91
        vessel._ingest_ais_event(event)
        self.assertEqual(vessel.ais_latitude,-20)
        vessel.ais_reported_at=now-timedelta(days=1)
        self.assertFalse(shipment._voyage_control_values(date(2026,10,16))['ais_fresh'])
        with self.assertRaises(ValidationError),self.cr.savepoint():
            vessel.mmsi='invalid'
        vessel.mmsi='999000090'
        self.assertFalse(vessel.ais_reported_at)
        self.assertFalse(shipment._voyage_control_values(date(2026,10,16))['ais_position'])
        other=self.env['res.company'].create({'name':'QA otra empresa paneles'})
        route=self.env['step.export.sea.route'].create({'name':'QA confidencial','company_id':other.id,
            'origin_port_id':self.env['l10n_cl.customs_port'].search([],limit=1).id,
            'destination_port_id':self.env['l10n_cl.customs_port'].search([],limit=1).id})
        user=self.env['res.users'].with_context(no_reset_password=True).create({'name':'QA operador paneles','login':'qa-t8990-operator',
            'company_id':self.env.company.id,'company_ids':[Command.set(self.env.company.ids)],'groups_id':[Command.set(self.env.ref('base.group_user').ids)]})
        self.assertFalse(self.env['step.export.sea.route'].with_user(user).search([('id','=',route.id)]))
        with self.assertRaises(AccessError):
            route.with_user(user).read(['name'])
