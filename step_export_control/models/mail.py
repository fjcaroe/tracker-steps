"""A queued mail or a printed PDF is never counted as a delivered document."""
import base64
from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError


class Message(models.Model):
    _inherit='mail.message'
    export_control_type_ids=fields.Many2many('step.export.document.type',string='Documentos exportación enviados')


class Compose(models.TransientModel):
    _inherit='mail.compose.message'
    export_control_type_ids=fields.Many2many('step.export.document.type',string='Documentos de este correo')

    def _prepare_mail_values(self,res_ids):
        values=super()._prepare_mail_values(res_ids)
        if self.export_control_type_ids:
            allowed={'sale.order':{'pf','invoice'},'account.move':{'fx'},
                     'step.export.export':{'ie','pl','bl','bl_nv','bl_v','bill','phyto','origin','dus','other'}}
            if not set(self.export_control_type_ids.mapped('kind'))<=allowed.get(self.model,set()):
                raise ValidationError(_('Seleccione los tipos de documento correspondientes a esta aplicación.'))
            for vals in values.values():
                if not vals.get('attachment_ids'):
                    raise ValidationError(_('Adjunte los documentos antes de enviar el correo de control.'))
                vals['export_control_type_ids']=[Command.set(self.export_control_type_ids.ids)]
        return values


class Mail(models.Model):
    _inherit='mail.mail'

    def _postprocess_sent_message(self,success_pids,failure_reason=False,failure_type=None):
        # Capture evidence before the native hook removes auto-delete mail rows.
        for mail in self.filtered(lambda m:m.state=='sent' and bool(m.attachment_ids)):
            if failure_type or failure_reason:
                continue
            shipment=self.env['step.export.export']
            types=mail.export_control_type_ids
            if mail.model=='step.export.export':
                shipment=shipment.browse(mail.res_id).exists()
            elif mail.model=='sale.order':
                order=self.env['sale.order'].browse(mail.res_id).exists()
                shipment=order.step_export_shipment_id or self.env['step.export.export'].search([('folio_sale_order_id','=',order.id)]) if order else shipment
            elif mail.model=='account.move':
                invoice=self.env['account.move'].browse(mail.res_id).exists()
                shipment=invoice.step_export_shipment_id if invoice and invoice.move_type=='out_invoice' else shipment
                if shipment and not types:
                    types=self.env['step.export.document.type'].search([('kind','=','fx')])
            if not shipment or not types:
                continue
            shipment.action_complete_document_control()
            today=fields.Date.context_today(mail)
            for line in shipment.documentation_ids.filtered(lambda l:l.kind in types.mapped('kind')):
                if line.effective_sent_on:
                    continue  # first actual delivery controls the deadline
                created=min(mail.attachment_ids.mapped('create_date'))
                line.write({'sent_on':today,'sent_message_id':mail.mail_message_id.id,
                    'sent_attachment_ids':[Command.set(mail.attachment_ids.ids)],
                    'document_created_on':line.document_created_on or fields.Date.context_today(mail,created)})
        return super()._postprocess_sent_message(success_pids,failure_reason,failure_type)


class Order(models.Model):
    _inherit='sale.order'

    def _prepare_control_report_email(self,kind,report):
        self.ensure_one()
        self._check_commercial_ready()
        pdf,_format=self.env['ir.actions.report']._render_qweb_pdf(report,self.ids)
        parameter=self.env['step.export.document.type'].search([('kind','=',kind)],limit=1)
        attachment=self.env['ir.attachment'].create({'name':parameter.name+' '+self.name+'.pdf',
            'type':'binary','datas':base64.b64encode(pdf),'mimetype':'application/pdf','res_model':self._name,'res_id':self.id})
        return {'type':'ir.actions.act_window','res_model':'mail.compose.message','view_mode':'form','target':'new',
            'context':{'default_model':self._name,'default_res_ids':self.ids,'default_composition_mode':'comment',
                'default_partner_ids':[Command.set(self.partner_id.ids)],'default_attachment_ids':[Command.set(attachment.ids)],
                'default_export_control_type_ids':[Command.set(parameter.ids)],'force_email':True}}

    def action_control_email_proforma(self):
        return self._prepare_control_report_email('pf','step_sale_export_report.action_proforma')

    def action_control_email_invoice(self):
        return self._prepare_control_report_email('invoice','step_export_document_revision.action_commercial_invoice')
