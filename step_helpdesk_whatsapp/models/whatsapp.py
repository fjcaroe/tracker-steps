import base64
from datetime import datetime, timedelta
import hashlib
import mimetypes
import re
import threading
import uuid
from psycopg2.extras import Json
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import plaintext2html
from ..provider import MetaCloudProvider, MockWhatsAppProvider, ProviderError, MIME, event_key

PRIVATE = object()


class Channel(models.Model):
    _name='step.helpdesk.wa.channel'
    _description='Canal de soporte WhatsApp'
    _check_company_auto=True
    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    team_id=fields.Many2one('helpdesk.team',required=True,check_company=True)
    provider=fields.Selection([('mock','Simulación'),('meta_cloud','Meta Cloud API')],required=True,default='mock')
    enabled=fields.Boolean(string='Habilitado',default=False)
    pause_outgoing=fields.Boolean(string='Pausar envíos',default=False)
    route_key=fields.Char(default=lambda s:uuid.uuid4().hex,required=True,copy=False,readonly=True)
    account_id=fields.Char(string='WABA ID')
    phone_number_id=fields.Char(string='Phone Number ID')
    app_id=fields.Char(string='App ID')
    graph_version=fields.Char(string='Versión Graph API',help='Versión soportada indicada por Meta al configurar la aplicación.')
    access_token=fields.Char(groups='base.group_system',copy=False)
    app_secret=fields.Char(groups='base.group_system',copy=False)
    verify_token=fields.Char(groups='base.group_system',copy=False,default=lambda s:uuid.uuid4().hex)
    callback_url=fields.Char(compute='_compute_callback')
    reception_hours=fields.Char(string='Horario de atención')
    auto_receipt=fields.Boolean(string='Confirmar recepción una vez por caso',default=False)
    max_media_mb=fields.Integer(default=16,string='Máximo archivo (MB)')
    retention_days=fields.Integer(default=30,string='Retención del evento original (días)')
    _sql_constraints=[('route_unique','unique(route_key)','La ruta ya está asignada.')]

    def _compute_callback(self):
        for c in self:
            c.callback_url=c.get_base_url()+'/whatsapp/webhook/'+c.route_key

    @api.constrains('enabled','provider','company_id','team_id','access_token','app_secret','verify_token','app_id','account_id','phone_number_id','graph_version','max_media_mb','retention_days')
    def _check_configuration(self):
        for c in self:
            if c.team_id.company_id!=c.company_id or not 1<=c.max_media_mb<=16 or not 1<=c.retention_days<=365:
                raise ValidationError(_('Revise empresa/equipo y límites del canal.'))
            if c.enabled and c.provider=='meta_cloud' and not all([c.access_token,c.app_secret,c.verify_token,c.account_id,c.phone_number_id,c.app_id,re.fullmatch(r'v\d{1,2}\.0',c.graph_version or '')]):
                raise ValidationError(_('Complete los datos de Cloud API antes de habilitar el canal.'))

    def _transport(self):
        self.ensure_one()
        return MockWhatsAppProvider(self) if self.provider=='mock' else MetaCloudProvider(self)

    def write(self, values):
        if set(values)&{'provider','team_id','company_id','account_id','phone_number_id','route_key'}:
            for channel in self:
                if self.env['step.helpdesk.wa.conversation'].sudo().search_count([('channel_id','=',channel.id)]):
                    raise UserError(_('Cree otro canal para cambiar número, proveedor, empresa o equipo. El historial conserva su destino.'))
        return super().write(values)

    def _ingest(self, events):
        self.ensure_one()
        Event=self.env['step.helpdesk.wa.event'].sudo()
        for event in events:
            key=event_key(event)
            self.env.cr.execute('''INSERT INTO step_helpdesk_wa_event
                (channel_id,company_id,team_id,dedupe_key,payload,kind,state,attempts,create_uid,write_uid,create_date,write_date)
                VALUES (%s,%s,%s,%s,%s,%s,'pending',0,%s,%s,%s,%s)
                ON CONFLICT (channel_id,dedupe_key) DO NOTHING''',[
                self.id,self.company_id.id,self.team_id.id,key,Json(event),event['kind'],
                self.env.uid,self.env.uid,fields.Datetime.now(),fields.Datetime.now()])
        Event.invalidate_model()

    def action_sync_templates(self):
        self.ensure_one();self.check_access('write')
        if not self.enabled:
            raise UserError(_('Habilite el canal después de configurar Cloud API.'))
        for data in self._transport().templates():
            if not data.get('name') or not data.get('language'):
                continue
            Template=self.env['step.helpdesk.wa.template']
            domain=[('channel_id','=',self.id),('name','=',data['name']),('language','=',data['language'])]
            values={'approved':data.get('status')=='APPROVED','purpose':data.get('category','')}
            existing=Template.search(domain)
            if existing:existing.with_context(_wa_private=PRIVATE).write(values)
            else:Template.with_context(_wa_private=PRIVATE).create(dict(values,channel_id=self.id,name=data['name'],language=data['language']))
        return True

    def _cron_process(self):
        Event=self.env['step.helpdesk.wa.event'].sudo()
        now=fields.Datetime.now()
        self.env.cr.execute("SELECT id FROM step_helpdesk_wa_event WHERE state='pending' AND (next_attempt IS NULL OR next_attempt<=%s) ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED",[now])
        for row in self.env.cr.fetchall():
            event=Event.browse(row[0])
            if not event.channel_id.enabled:continue
            try:
                with self.env.cr.savepoint():
                    event._process()
                    event.write({'state':'done','error':False})
            except Exception:
                # Keep content private. A failed classifier never loses an event.
                event.write({'attempts':event.attempts+1,'state':'failed' if event.attempts>=4 else 'pending',
                    'next_attempt':now+timedelta(minutes=2**min(event.attempts,6)),'error':'processing_error'})
        Message=self.env['step.helpdesk.wa.message'].sudo()
        self.env.cr.execute("SELECT id FROM step_helpdesk_wa_message WHERE state='processing' AND attempted_at<%s FOR UPDATE SKIP LOCKED",[now-timedelta(minutes=5)])
        Message.browse([r[0] for r in self.env.cr.fetchall()]).write({'state':'uncertain','error':'worker_interrupted'})
        self.env.cr.execute("SELECT id FROM step_helpdesk_wa_message WHERE direction='outgoing' AND state='pending' AND (next_attempt IS NULL OR next_attempt<=%s) ORDER BY id LIMIT 20 FOR UPDATE SKIP LOCKED",[now])
        for row in self.env.cr.fetchall():
            message=Message.browse(row[0])
            if not message.channel_id.enabled or message.channel_id.pause_outgoing:continue
            try:message._send()
            except Exception:
                message.write({'state':'uncertain','error':'unexpected_transport_error'})
        for channel in self.search([]):
            Event.search([('channel_id','=',channel.id),('state','=', 'done'),('create_date','<',now-timedelta(days=channel.retention_days))]).write({'payload':False})
        Message.search([('direction','=','incoming'),('media_state','=','pending'),('next_attempt','<=',now)],limit=20)._fetch_media()


class Conversation(models.Model):
    _name='step.helpdesk.wa.conversation'
    _description='Conversación de soporte WhatsApp'
    _rec_name='sender_id'
    channel_id=fields.Many2one('step.helpdesk.wa.channel',required=True,ondelete='restrict')
    company_id=fields.Many2one(related='channel_id.company_id',store=True)
    team_id=fields.Many2one(related='channel_id.team_id',store=True)
    sender_id=fields.Char(required=True,index=True)
    partner_id=fields.Many2one('res.partner',readonly=True)
    last_incoming=fields.Datetime(readonly=True)
    consent=fields.Boolean(string='Consentimiento para seguimiento con plantilla')
    consent_by=fields.Many2one('res.users',readonly=True)
    consent_at=fields.Datetime(readonly=True)
    identity_verified_by=fields.Many2one('res.users',readonly=True)
    identity_verified_at=fields.Datetime(readonly=True)
    _sql_constraints=[('sender_unique','unique(channel_id,sender_id)','La conversación ya existe.')]

    def write(self, values):
        if not self.env.su and self.env.context.get('_wa_private') is not PRIVATE:
            if set(values)-{'consent'}:raise AccessError(_('Solo puede registrar o retirar el consentimiento.'))
            values=dict(values,consent_by=self.env.user.id,consent_at=fields.Datetime.now())
        return super().write(values)


class Template(models.Model):
    _name='step.helpdesk.wa.template'
    _description='Plantilla WhatsApp de soporte'
    channel_id=fields.Many2one('step.helpdesk.wa.channel',required=True)
    company_id=fields.Many2one(related='channel_id.company_id',store=True)
    team_id=fields.Many2one(related='channel_id.team_id',store=True)
    name=fields.Char(required=True)
    language=fields.Char(required=True,default='es')
    approved=fields.Boolean(readonly=True)
    purpose=fields.Char(readonly=True)
    _sql_constraints=[('template_unique','unique(channel_id,name,language)','La plantilla ya existe.')]

    @api.model_create_multi
    def create(self, values):
        if self.env.context.get('_wa_private') is not PRIVATE and any(v.get('approved') for v in values):
            raise AccessError(_('La aprobación se obtiene al sincronizar con Meta.'))
        return super().create(values)

    def write(self, values):
        if 'approved' in values and self.env.context.get('_wa_private') is not PRIVATE:
            raise AccessError(_('La aprobación se obtiene al sincronizar con Meta.'))
        return super().write(values)


class Event(models.Model):
    _name='step.helpdesk.wa.event'
    _description='Cola privada de eventos WhatsApp'
    channel_id=fields.Many2one('step.helpdesk.wa.channel',required=True,ondelete='restrict')
    company_id=fields.Many2one(related='channel_id.company_id',store=True)
    team_id=fields.Many2one(related='channel_id.team_id',store=True)
    dedupe_key=fields.Char(required=True)
    kind=fields.Selection([('incoming','Entrada'),('status','Estado')],required=True)
    payload=fields.Json(groups='base.group_system')
    state=fields.Selection([('pending','Pendiente'),('done','Procesado'),('failed','Revisar')],default='pending')
    attempts=fields.Integer(default=0)
    next_attempt=fields.Datetime()
    error=fields.Char()
    _sql_constraints=[('event_unique','unique(channel_id,dedupe_key)','El evento ya se recibió.')]

    def action_retry(self):
        self.check_access('write')
        for event in self:
            if event.state!='failed' or not event.payload:
                raise UserError(_('Solo se reintentan eventos pendientes de revisión que conservan su contenido.'))
        self.write({'state':'pending','attempts':0,'next_attempt':False,'error':False})
        return True

    def _process(self):
        self.ensure_one();data=self.payload
        channel=self.channel_id
        Message=self.env['step.helpdesk.wa.message'].sudo()
        if self.kind=='status':
            domain=[('channel_id','=',channel.id),('direction','=','outgoing')]
            message=Message.search(domain+[('external_id','=',data['external_id'])],limit=1)
            if not message and data.get('local_id'):
                message=Message.search(domain+[('local_id','=',data['local_id']),('conversation_id.sender_id','=',data.get('sender'))],limit=1)
            if message:
                if data.get('sender')!=message.conversation_id.sender_id:return
                message._status(data)
            else:
                # Statuses can arrive before a worker commits the send result.
                if self.attempts<5:raise UserError(_('Estado pendiente de vincular al envío.'))
            return
        # Serialize different events for a sender, not only repeated IDs.
        key=int.from_bytes(hashlib.sha256((str(channel.id)+':'+data['sender']).encode()).digest()[:8],'big',signed=True)
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)',[key])
        if Message.search_count([('channel_id','=',channel.id),('direction','=','incoming'),('external_id','=',data['external_id'])]):return
        Conversation=self.env['step.helpdesk.wa.conversation'].sudo()
        conversation=Conversation.search([('channel_id','=',channel.id),('sender_id','=',data['sender'])],limit=1)
        if not conversation:
            # Never identify by a visible name. Ambiguous phone matches stay unlinked.
            partner=self.env['res.partner']
            if re.fullmatch(r'\+\d{8,15}',data.get('sender_phone') or ''):
                candidates=self.env['res.partner'].sudo().search([('company_id','in',[False,channel.company_id.id]),('phone_sanitized','=',data['sender_phone'])],limit=2)
                if len(candidates)==1:partner=candidates
            conversation=Conversation.create({'channel_id':channel.id,'sender_id':data['sender'],'partner_id':partner.id})
        when=datetime.utcfromtimestamp(int(data.get('timestamp') or 0))
        if not conversation.last_incoming or when>conversation.last_incoming:
            conversation.last_incoming=min(when,fields.Datetime.now())
        Ticket=self.env['helpdesk.ticket'].sudo().with_company(channel.company_id).with_context(_wa_private=PRIVATE)
        tickets=Ticket.search([('step_wa_conversation_id','=',conversation.id),('team_id','=',channel.team_id.id),('stage_id.fold','=',False)])
        target=self.env['helpdesk.ticket']
        previous=self.env['helpdesk.ticket']
        if data.get('reply_to'):
            reply=Message.search([('channel_id','=',channel.id),('conversation_id','=',conversation.id),('external_id','=',data['reply_to'])],limit=1)
            if reply.ticket_id in tickets:target=reply.ticket_id
        reference=re.search(r'(?:ticket|caso)\s*#?\s*(\d+)\b',data.get('text',''),re.I)
        if not target and reference:
            target=tickets.filtered(lambda t:t.id==int(reference[1]))
            if not target:
                tickets=self.env['helpdesk.ticket']  # Untrusted reference requires classification.
        elif not target and len(tickets)==1:target=tickets
        new=False
        if not target and not tickets and not reference:
            previous=Ticket.search([('step_wa_conversation_id','=',conversation.id),('team_id','=',channel.team_id.id)],order='id desc',limit=1)
            target=Ticket.with_context(mail_create_nosubscribe=True,mail_notify_noemail=True).create({
                'name':(data.get('text') or 'Soporte WhatsApp — nuevo caso')[:100], 'team_id':channel.team_id.id,
                'partner_id':conversation.partner_id.id,'step_wa_conversation_id':conversation.id,
                'step_wa_previous_ticket_id':previous.id})
            new=True
        message=Message.with_context(_wa_private=PRIVATE).create({'channel_id':channel.id,'conversation_id':conversation.id,
            'ticket_id':target.id,'external_id':data['external_id'],'direction':'incoming','state':'received',
            'kind':data['type'] if data['type'] in MIME or data['type']=='text' else 'unsupported',
            'text':data.get('text') or '', 'occurred_at':when,'media_id':data.get('media_id'),
            'mime':data.get('mime'),'filename':data.get('filename'),
            'media_state':'pending' if data.get('media_id') else 'none','next_attempt':fields.Datetime.now()})
        if target:message._post_incoming()
        if new and channel.auto_receipt:
            Message.with_context(_wa_private=PRIVATE).create({'channel_id':channel.id,'conversation_id':conversation.id,
                'ticket_id':target.id,'direction':'outgoing','kind':'text',
                'text':_('Recibimos su solicitud. Caso #%s. %s',target.id,channel.reception_hours or ''),'requested_by':self.env.ref('base.user_root').id})


class Message(models.Model):
    _name='step.helpdesk.wa.message'
    _description='Mensaje de soporte WhatsApp'
    _order='id desc'
    channel_id=fields.Many2one('step.helpdesk.wa.channel',required=True,ondelete='restrict')
    conversation_id=fields.Many2one('step.helpdesk.wa.conversation',required=True,ondelete='restrict')
    company_id=fields.Many2one(related='channel_id.company_id',store=True)
    team_id=fields.Many2one(related='channel_id.team_id',store=True)
    ticket_id=fields.Many2one('helpdesk.ticket',ondelete='restrict')
    local_id=fields.Char(default=lambda s:uuid.uuid4().hex,required=True,copy=False)
    external_id=fields.Char(index=True,copy=False)
    direction=fields.Selection([('incoming','Entrante'),('outgoing','Saliente')],required=True)
    kind=fields.Selection([('text','Texto'),('image','Imagen'),('document','Documento'),('audio','Audio'),('template','Plantilla'),('unsupported','Tipo no soportado')],required=True)
    text=fields.Text()
    occurred_at=fields.Datetime(default=fields.Datetime.now)
    state=fields.Selection([(x,y) for x,y in [('pending','Pendiente'),('processing','Enviando'),('accepted','Aceptado por Meta'),('delivered','Entregado'),('read','Leído'),('received','Recibido'),('failed','Revisar'),('uncertain','Envío incierto')]],default='pending')
    requested_by=fields.Many2one('res.users',readonly=True)
    attempts=fields.Integer(default=0)
    attempted_at=fields.Datetime()
    next_attempt=fields.Datetime()
    error=fields.Char()
    mail_message_id=fields.Many2one('mail.message',readonly=True)
    template_id=fields.Many2one('step.helpdesk.wa.template')
    template_parameters=fields.Json()
    attachment_id=fields.Many2one('ir.attachment',readonly=True)
    media_id=fields.Char()
    mime=fields.Char()
    filename=fields.Char()
    media_state=fields.Selection([('none','Sin archivo'),('pending','Archivo pendiente'),('done','Archivo recibido'),('failed','Revisar archivo')],default='none')
    _sql_constraints=[('message_unique','unique(channel_id,direction,external_id)','El mensaje ya existe.'),('local_unique','unique(local_id)','El envío ya existe.')]

    @api.model_create_multi
    def create(self, values):
        if self.env.context.get('_wa_private') is not PRIVATE:raise AccessError(_('Use la acción Responder por WhatsApp.'))
        return super().create(values)

    def _post_incoming(self):
        self.ensure_one()
        if self.mail_message_id:return
        message=self.ticket_id.with_context(_wa_private=PRIVATE,mail_notify_noemail=True,mail_post_autofollow=False).message_post(
            body=plaintext2html(self.text or _('Archivo de WhatsApp (estado en la pestaña WhatsApp).')),
            message_type='email',subtype_xmlid='mail.mt_comment',author_id=self.conversation_id.partner_id.id or False,
            email_from='WhatsApp <whatsapp-incoming@invalid>',
            attachment_ids=self.attachment_id.ids)
        message.with_context(_wa_private=PRIVATE).write({'step_wa_inbound':True,'date':self.occurred_at})
        self.mail_message_id=message

    def _window_open(self):
        last=self.conversation_id.last_incoming
        return bool(last and fields.Datetime.now()<last+timedelta(hours=24))

    def _check_send(self):
        self.ensure_one()
        if self.conversation_id.channel_id!=self.channel_id or self.ticket_id.step_wa_conversation_id!=self.conversation_id:
            raise UserError(_('El mensaje y el ticket deben pertenecer a la misma conversación.'))
        if self.kind!='template' and not self._window_open():raise UserError(_('La ventana de 24 horas terminó. Use una plantilla aprobada con consentimiento.'))
        if self.kind=='template' and (not self.template_id.approved or self.template_id.channel_id!=self.channel_id or not self.conversation_id.consent):
            raise UserError(_('Revise la plantilla aprobada y el consentimiento del cliente.'))
        if self.kind=='text' and len(self.text or '')>4096:
            raise UserError(_('La respuesta debe tener como máximo 4096 caracteres.'))

    def _send(self):
        self.ensure_one()
        self.flush_recordset(['state'])
        self.env.cr.execute('SELECT state FROM step_helpdesk_wa_message WHERE id=%s FOR UPDATE SKIP LOCKED',[self.id])
        row=self.env.cr.fetchone()
        if not row or row[0]!='pending':return
        self.invalidate_recordset(['state'])
        try:self._check_send()
        except UserError:
            self.write({'state':'failed','error':'window_or_scope_invalid'});return
        self.write({'state':'processing','attempted_at':fields.Datetime.now(),'attempts':self.attempts+1})
        # Odoo caches writes. Persist the lease before a remote side effect;
        # an interrupted process must never leave the send looking pending.
        self.flush_recordset(['state','attempted_at','attempts'])
        if not getattr(threading.current_thread(),'testing',False):
            self.env.flush_all()
            self.env.cr.commit()
        try:
            external=self.channel_id._transport().send(self)
            self.invalidate_recordset(['state'])
            values={'external_id':external,'error':False}
            if self.state not in ('delivered','read'):values['state']='accepted'
            self.write(values)
        except ProviderError as e:
            self.write({'state':'uncertain' if e.uncertain else 'pending' if e.retry and self.attempts<5 else 'failed',
                'next_attempt':fields.Datetime.now()+timedelta(minutes=2**min(self.attempts,6)),'error':e.code})

    def _status(self, event):
        self.ensure_one()
        ranks={'pending':0,'processing':0,'uncertain':0,'failed':0,'accepted':1,'delivered':2,'read':3}
        state={'sent':'accepted','delivered':'delivered','read':'read','failed':'failed'}.get(event['status'])
        if state and ((state=='failed' and ranks.get(self.state,0)<=1) or (state!='failed' and ranks.get(state,0)>=ranks.get(self.state,0))):
            self.write({'state':state,'external_id':event['external_id']})

    def _fetch_media(self):
        for message in self:
            self.env.cr.execute("SELECT id FROM step_helpdesk_wa_message WHERE id=%s AND media_state='pending' FOR UPDATE SKIP LOCKED",[message.id])
            if not self.env.cr.fetchone():continue
            message.invalidate_recordset(['media_state','attachment_id'])
            if not message.channel_id.enabled or message.media_state!='pending':continue
            try:
                if message.mime not in MIME.get(message.kind,set()):raise ProviderError('unsupported_media_type')
                raw=message.channel_id._transport().download(message.media_id,message.mime)
                extension=mimetypes.guess_extension(message.mime) or ''
                attachment=self.env['ir.attachment'].sudo().create({'name':(message.filename or message.kind+extension).split('/')[-1].split('\\')[-1],
                    'datas':base64.b64encode(raw),'mimetype':message.mime,'public':False,
                    'res_model':'step.helpdesk.wa.message','res_id':message.id})
                message.write({'attachment_id':attachment.id,'media_state':'done','error':False})
                if message.mail_message_id:
                    message.mail_message_id.write({'attachment_ids':[(4,attachment.id)]})
            except ProviderError as e:
                message.write({'media_state':'pending' if e.retry and message.attempts<5 else 'failed',
                    'attempts':message.attempts+1,'error':e.code,'next_attempt':fields.Datetime.now()+timedelta(minutes=5)})

    def action_assign_ticket(self):
        self.ensure_one();self.check_access('read')
        return {'type':'ir.actions.act_window','res_model':'step.helpdesk.wa.classify','view_mode':'form','target':'new','context':{'default_message_id':self.id}}


class Ticket(models.Model):
    _inherit='helpdesk.ticket'
    step_wa_conversation_id=fields.Many2one('step.helpdesk.wa.conversation',readonly=True)
    step_wa_previous_ticket_id=fields.Many2one('helpdesk.ticket',readonly=True)
    step_wa_message_ids=fields.One2many('step.helpdesk.wa.message','ticket_id',readonly=True)

    @api.model_create_multi
    def create(self, values):
        if any(v.get('step_wa_conversation_id') for v in values) and self.env.context.get('_wa_private') is not PRIVATE:
            raise AccessError(_('La conversación se vincula mediante el receptor o el asistente de clasificación.'))
        return super().create(values)

    def write(self, values):
        if 'step_wa_conversation_id' in values and self.env.context.get('_wa_private') is not PRIVATE:
            raise AccessError(_('La conversación se vincula mediante el receptor o el asistente de clasificación.'))
        return super().write(values)

    def action_respond_whatsapp(self):
        self.ensure_one();self.check_access('write')
        if not self.step_wa_conversation_id:raise UserError(_('Este ticket no tiene una conversación de WhatsApp.'))
        return {'type':'ir.actions.act_window','res_model':'step.helpdesk.wa.compose','view_mode':'form','target':'new','context':{'default_ticket_id':self.id}}


class MailMessage(models.Model):
    _inherit='mail.message'
    step_wa_inbound=fields.Boolean(readonly=True,index=True)

    @api.model_create_multi
    def create(self, values):
        if any(v.get('step_wa_inbound') for v in values) and self.env.context.get('_wa_private') is not PRIVATE:
            raise AccessError(_('La marca de entrada WhatsApp pertenece al receptor firmado.'))
        return super().create(values)

    def write(self, values):
        if values.get('step_wa_inbound') and self.env.context.get('_wa_private') is not PRIVATE:
            raise AccessError(_('La marca de entrada WhatsApp pertenece al receptor firmado.'))
        return super().write(values)


class Compose(models.TransientModel):
    _name='step.helpdesk.wa.compose'
    _description='Responder por WhatsApp'
    ticket_id=fields.Many2one('helpdesk.ticket',required=True,readonly=True)
    text=fields.Text(string='Respuesta')
    template_id=fields.Many2one('step.helpdesk.wa.template',string='Plantilla aprobada')
    parameters=fields.Char(string='Parámetros separados por |')
    attachment_id=fields.Many2one('ir.attachment',string='Archivo del ticket')

    def action_send(self):
        self.ensure_one();self.ticket_id.check_access('write')
        if not self.env.user.has_group('helpdesk.group_helpdesk_user'):raise AccessError(_('No tiene permiso de Helpdesk.'))
        conversation=self.ticket_id.step_wa_conversation_id
        channel=conversation.channel_id
        if not channel.enabled or channel.pause_outgoing:raise UserError(_('El canal no está habilitado para enviar.'))
        if not self.text and not self.template_id and not self.attachment_id:raise UserError(_('Escriba una respuesta o seleccione un archivo/plantilla.'))
        if self.template_id and self.attachment_id:raise UserError(_('Envíe el archivo separado de la plantilla.'))
        rows=[]
        if self.template_id or self.text:
            rows.append({'kind':'template' if self.template_id else 'text','text':self.text,
                'template_id':self.template_id.id,'template_parameters':(self.parameters or '').split('|') if self.parameters else []})
        if self.attachment_id:
            attachment=self.attachment_id;attachment.check_access('read')
            if attachment.res_model!='helpdesk.ticket' or attachment.res_id!=self.ticket_id.id or attachment.public:
                raise UserError(_('Seleccione un archivo privado de este ticket.'))
            kind=next((k for k,v in MIME.items() if attachment.mimetype in v),None)
            if not kind or attachment.file_size>channel.max_media_mb*1024*1024:raise UserError(_('Tipo o tamaño de archivo no permitido.'))
            rows.append({'kind':kind,'attachment_id':attachment.id})
        for row in rows:
            message=self.env['step.helpdesk.wa.message'].sudo().with_context(_wa_private=PRIVATE).create(dict(row,
                channel_id=channel.id,conversation_id=conversation.id,ticket_id=self.ticket_id.id,
                direction='outgoing',requested_by=self.env.user.id))
            message._check_send()
        return {'type':'ir.actions.act_window_close'}


class Classify(models.TransientModel):
    _name='step.helpdesk.wa.classify'
    _description='Clasificar mensaje WhatsApp'
    message_id=fields.Many2one('step.helpdesk.wa.message',required=True,readonly=True)
    ticket_id=fields.Many2one('helpdesk.ticket',string='Caso abierto de esta conversación')
    new_case=fields.Boolean(string='Abrir un caso nuevo')
    identity_verified=fields.Boolean(string='Confirmé que el solicitante es el titular de este caso')

    def action_apply(self):
        self.ensure_one();message=self.message_id;message.check_access('read')
        if message.direction!='incoming':raise UserError(_('Solo se clasifican entradas.'))
        conversation=message.conversation_id
        ticket=self.ticket_id
        if self.new_case:
            self.env['helpdesk.ticket'].check_access_rights('create')
            ticket=self.env['helpdesk.ticket'].with_context(_wa_private=PRIVATE).create({'name':(message.text or 'Soporte WhatsApp')[:100],
                'team_id':message.team_id.id,'step_wa_conversation_id':conversation.id})
        ticket.check_access('write')
        if not ticket or ticket.team_id!=message.team_id or ticket.stage_id.fold:
            raise UserError(_('Seleccione un caso abierto de la misma conversación y equipo.'))
        if ticket.step_wa_conversation_id and ticket.step_wa_conversation_id!=conversation:
            raise UserError(_('El caso pertenece a otra conversación.'))
        if not ticket.step_wa_conversation_id:
            if not self.identity_verified:raise UserError(_('Verifique la identidad del solicitante antes de vincular un caso recibido por otro canal.'))
            ticket.with_context(_wa_private=PRIVATE).write({'step_wa_conversation_id':conversation.id})
            conversation.sudo().write({'identity_verified_by':self.env.user.id,'identity_verified_at':fields.Datetime.now()})
        message.sudo().write({'ticket_id':ticket.id,'mail_message_id':False})
        message.sudo()._post_incoming()
        return {'type':'ir.actions.act_window_close'}
