import base64
import io
from zipfile import ZipFile
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError
from odoo.addons.step_packing_dispatch.tests.test_dispatch import DispatchCase
from ..models.instruction import ROLES


@tagged('post_install', '-at_install')
class InstructionCase(TransactionCase):
    def fixture(self):
        self.env = self.env(context=dict(self.env.context, tracking_disable=True,
            mail_create_nosubscribe=True, mail_notify_force_send=False, no_reset_password=True))
        DispatchCase.fixture(self)
        self.agent = self.env['res.partner'].create({'name': 'QA T95 agente',
            'step_export_customs_agent': True, 'step_export_customs_agent_code': '0012'})
        self.carrier = self.env['res.partner'].create({'name': 'QA T95 transportista', 'step_carga': True})
        self.shipment.write({'dus_folio': '009876', 'destination_country_id': self.env.ref('base.cl').id,
            'customs_agent_id': self.agent.id})
        self.plan.freight_carrier_id = self.carrier

    def test_header_source_and_guide(self):
        self.fixture()
        self.assertEqual(self.plan.dus_folio, '009876')
        self.assertEqual(self.plan.customs_agent_code, '0012')
        self.assertEqual(self.plan.destination_country_id, self.shipment.destination_country_id)
        self.assertEqual(self.plan.destination_port_id, self.shipment.destination_port_id)
        self.assertEqual(self.plan.action_create_guide()['context']['default_carrier_id'], self.carrier.id)
        self.agent.step_export_customs_agent_code = '0007'
        self.assertEqual(self.plan.customs_agent_code, '0007')
        self.assertEqual(self.shipment.line_ids.box_qty, 20)

    def test_six_role_codes_and_native_communications(self):
        self.fixture()
        for index, (role, _) in enumerate(ROLES):
            self.agent['step_export_' + role + '_code'] = '00' + str(index)
        self.assertEqual(self.agent.step_export_customs_agent_code, '005')
        attachment = self.env['ir.attachment'].create({'name': 'QA T95.txt', 'datas': base64.b64encode(b'QA'),
            'res_model': self.plan._name, 'res_id': self.plan.id})
        message = self.plan.message_post(body='QA T95 nota interna', subtype_xmlid='mail.mt_note',
            attachment_ids=attachment.ids, partner_ids=[])
        self.assertIn(message, self.plan.message_ids)
        self.assertIn(attachment, message.attachment_ids)
        self.assertFalse(message.notification_ids)

    def test_reports_include_all_load_columns_and_totals(self):
        self.fixture()
        self.plan.load_line_ids.write({'label': '=HYPERLINK("https://invalid","bad")'})
        with ZipFile(io.BytesIO(self.plan._dispatch_xlsx())) as book:
            strings = book.read('xl/sharedStrings.xml').decode()
            worksheet = book.read('xl/worksheets/sheet1.xml').decode()
        for text in ('Instructivo de despacho', 'Número DUS', '009876', '0012', 'Productor',
                     'Variedad', 'Marca', 'Calibre', 'Calidad', 'Cajas por pallet', 'Kg por caja',
                     'Pallets por camión', 'Cantidad camiones', 'Kilos'):
            self.assertIn(text, strings)
        self.assertNotIn('<f>', worksheet)
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'step_packing_dispatch_improvements.instruction_report', self.plan.ids)
        for text in ('009876', '0012', 'Carga solicitada', 'Cantidad camiones'):
            self.assertIn(text, html.decode())
        self.assertEqual(self.plan.action_dispatch_pdf()['report_type'], 'qweb-pdf')
        action = self.plan.action_dispatch_xlsx()
        attachment = self.env['ir.attachment'].browse(int(action['url'].split('/')[3].split('?')[0]))
        self.assertEqual((attachment.res_model, attachment.res_id), (self.plan._name, self.plan.id))
        self.assertFalse(attachment.public)

    def test_cross_company_download_denied(self):
        self.fixture()
        other = self.env['res.company'].create({'name': 'QA T95 otra empresa'})
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'QA T95 usuario', 'login': 'qa-t95-download', 'company_id': other.id,
            'company_ids': [Command.set(other.ids)], 'groups_id': [Command.set([
                self.env.ref('base.group_user').id, self.env.ref('stock.group_stock_manager').id])]})
        with self.assertRaises(AccessError):
            self.plan.with_user(user).with_context(allowed_company_ids=other.ids)._dispatch_xlsx()
        with self.assertRaises(AccessError):
            self.plan.with_user(user).with_context(allowed_company_ids=other.ids).action_dispatch_pdf()
