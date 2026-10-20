"""T95 reuses shipment/contact masters and native Odoo communications."""
import base64
import io
import xlsxwriter
from odoo import fields, models, _

ROLES = (
    ('receiver', 'Recibidor'), ('carrier', 'Naviera o aerolínea'),
    ('consignee', 'Consignatario'), ('notify', 'Notify'),
    ('forwarder', 'Agencia de carga'), ('customs_agent', 'Agente aduana'),
)
COLUMNS = (
    ('product_id', 'Producto'), ('packaging_id', 'Embalaje'),
    ('producer_id', 'Productor'), ('variety_id', 'Variedad'), ('label', 'Marca'),
    ('caliber_id', 'Calibre'), ('quality_id', 'Calidad'),
    ('pallet_qty', 'Pallets'), ('boxes_per_pallet', 'Cajas por pallet'),
    ('kg_per_box', 'Kg por caja'), ('box_qty', 'Cajas'), ('kg_qty', 'Kilos'),
)


class Partner(models.Model):
    _inherit = 'res.partner'
    for role, label in ROLES:
        locals()['step_export_' + role + '_code'] = fields.Char(string='Código ' + label)


class Instruction(models.Model):
    _name = 'step.export.dispatch.order'
    _inherit = ['step.export.dispatch.order', 'mail.thread', 'mail.activity.mixin']

    dus_folio = fields.Char(related='shipment_id.dus_folio', string='Número DUS')
    destination_country_id = fields.Many2one(related='shipment_id.destination_country_id', string='País destino')
    destination_port_id = fields.Many2one(related='shipment_id.destination_port_id', string='Puerto destino')
    customs_agent_id = fields.Many2one(related='shipment_id.customs_agent_id', string='Agente de aduana')
    customs_agent_code = fields.Char(related='customs_agent_id.step_export_customs_agent_code', string='Código Agente aduana')
    freight_carrier_id = fields.Many2one('res.partner', string='Transportista',
        domain=[('step_carga', '=', True)], check_company=True, tracking=True)

    def action_create_guide(self):
        action = super().action_create_guide()
        if self.freight_carrier_id:
            action['context']['default_carrier_id'] = self.freight_carrier_id.id
        return action

    def _dispatch_report_header(self):
        self.ensure_one()
        names = ('name', 'shipment_id', 'date', 'company_id', 'species_id',
                 'vessel_id', 'port_id', 'season_id', 'transport_type',
                 'receiver_id', 'user_id', 'dus_folio', 'destination_country_id',
                 'destination_port_id', 'customs_agent_id', 'customs_agent_code',
                 'freight_carrier_id')
        result = []
        for name in names:
            field = self._fields[name]
            value = self[name]
            if field.type == 'many2one':
                value = value.display_name
            elif field.type == 'selection':
                value = dict(field._description_selection(self.env)).get(value)
            result.append((field.get_description(self.env)['string'], value or ''))
        return result

    def _dispatch_report_columns(self):
        return COLUMNS

    def _dispatch_xlsx(self):
        self.ensure_one()
        self.check_access('read')
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
        sheet = book.add_worksheet('Instructivo de despacho')
        title = book.add_format({'bold': True, 'font_size': 16})
        label = book.add_format({'bold': True, 'bg_color': '#E8EFEC', 'text_wrap': True})
        text = book.add_format({'text_wrap': True, 'valign': 'top'})
        number = book.add_format({'num_format': '#,##0.00'})
        sheet.set_column(0, 6, 22)
        sheet.set_column(7, 11, 17)
        sheet.merge_range(0, 0, 0, 11, 'Instructivo de despacho', title)
        row = 2
        for key, value in self._dispatch_report_header():
            sheet.write_string(row, 0, key, label)
            sheet.merge_range(row, 1, row, 5, str(value), text)
            row += 1
        row += 1
        for col, (_, name) in enumerate(COLUMNS):
            sheet.write_string(row, col, name, label)
        sheet.set_row(row, 30)
        sheet.freeze_panes(row + 1, 0)
        first = row
        for line in self.load_line_ids:
            row += 1
            sheet.set_row(row, 45)
            for col, (name, _) in enumerate(COLUMNS):
                value = line[name]
                if line._fields[name].type in ('integer', 'float'):
                    sheet.write_number(row, col, value, number)
                else:
                    sheet.write_string(row, col, str(value.display_name or '') if line._fields[name].type == 'many2one' else str(value or ''), text)
        sheet.autofilter(first, 0, row, 11)
        row += 2
        for key, value in (('Pallets por camión', self.pallets_per_truck), ('Cantidad camiones', self.truck_qty),
                           ('Pallets', self.pallet_qty), ('Cajas', self.box_qty), ('Kilos', self.kg_qty)):
            sheet.write_string(row, 0, key, label)
            sheet.write_number(row, 1, value, number)
            row += 1
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.repeat_rows(first)
        book.close()
        return stream.getvalue()

    def action_dispatch_xlsx(self):
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': 'Instructivo de despacho - %s.xlsx' % self.id,
            'datas': base64.b64encode(self._dispatch_xlsx()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name, 'res_id': self.id,
        })
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}

    def action_dispatch_pdf(self):
        self.ensure_one()
        self.check_access('read')
        return self.env.ref('step_packing_dispatch_improvements.instruction_report').report_action(self, config=False)
