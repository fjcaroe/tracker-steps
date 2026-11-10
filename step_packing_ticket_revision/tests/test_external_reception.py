import base64
from io import BytesIO

from openpyxl import Workbook

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class ExternalReceiptCase(TransactionCase):
    def test_external_file_creates_native_draft_and_stock_only_on_validation(self):
        company = self.env.company
        company.step_fruit_inventory_enabled = True
        wh = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        producer = self.env['res.partner'].create({'name': 'QA T189 Productor', 'is_productor': True})
        packing = self.env['res.partner'].create({'name': 'QA T189 Packing', 'step_export_packing': True})
        fundo = self.env['step.fundo'].create({'name': 'QA T189 Fundo', 'partner_id': producer.id})
        species = self.env['step.especie'].create({
            'name': 'QA T189 Especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h',
        })
        group = self.env['step.grupo.variedad'].create({'name': 'QA T189 grupo', 'especie_id': species.id})
        varieties = self.env['step.variedad'].create([
            {'name': f'QA T189 {name}', 'cod_variedad': f'T189-{name}',
             'especie_id': species.id, 'grupo_variedad_id': group.id}
            for name in ('Azul', 'Verde')
        ])
        kg = self.env.ref('uom.product_uom_kgm')
        product = self.env['product.product'].create({'name': 'QA T189 Fruta',
            'is_storable': True, 'uom_id': kg.id, 'uom_po_id': kg.id, 'tracking': 'lot'})
        packaging = self.env['product.packaging'].create({'name': 'QA T189 Rejilla', 'product_id': product.id, 'qty': 3})
        category = self.env['step.management.fruit.category'].create({'name': 'QA T189 Categoría', 'code': 'T189'})
        fruit_class = self.env['step.management.fruit.class'].create({'name': 'QA T189 Clase', 'code': 'T189', 'category_id': category.id})
        season = self.env['step.temporada'].create({'name': 'QA T189 Temporada', 'code': 'T189'})

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['Encabezado anterior a la tabla'])
        sheet.append(['Folio Recep', 'N° Guía', 'N° Lote', 'Fecha/Hora Recep', 'Especie',
            'Variedad', 'Cliente', 'Productor', 'Envase', 'N° Cajas', 'KG Netos',
            'Tipo Recep', 'Concepto Fruta', 'Fruta Gasificada', 'Fruta Con Frio', 'Fruta Palletizada', 'Clasificación'])
        for index, variety in enumerate(varieties, 1):
            sheet.append(['QA189-01', 'QA189-GUIA', f'QA189-TARJA-{index}', '05-11-2026  02:43',
                species.name, variety.name, 'Cliente', 'Alias externo productor', 'Alias externo envase',
                10 * index, 20.5 * index, 'GRANEL PROCESO', 'CONVENCIONAL', 'N', 'S', 'S' if index == 1 else 'N', 'PSJ'])
        sheet.append([None] * 8 + ['>>Totales', 30, 61.5])
        workbook.create_sheet('descripción')
        def attachment():
            binary = BytesIO()
            workbook.save(binary)
            return base64.b64encode(binary.getvalue())

        model = self.env['step.external.fruit.reception.import']
        defaults = {
            'picking_type_id': wh.in_type_id.id, 'packing_id': packing.id, 'season_id': season.id,
            'product_id': product.id, 'category_id': category.id, 'fruit_class_id': fruit_class.id,
            'filename': 'qa189.xlsx',
        }
        sheet.cell(2, 11, 'Peso del packing')
        wizard = model.create(dict(defaults, file=attachment(), template_name='QA T193 externo'))
        wizard.action_review()
        manual = wizard.column_ids.filtered(lambda line: line.source == 'Peso del packing')
        self.assertFalse(manual.target)
        manual.target = 'kilos'
        wizard.action_review()
        wizard.alias_ids.filtered(lambda line: line.kind == 'producer').fundo_id = fundo
        wizard.alias_ids.filtered(lambda line: line.kind == 'packaging').packaging_id = packaging
        action = wizard.action_import()
        receipt = self.env['stock.picking'].browse(action['res_id'])
        self.assertEqual(receipt.state, 'draft')
        self.assertFalse(receipt.date_done)
        self.assertEqual(receipt.step_external_reception_folio, 'QA189-01')
        self.assertEqual(str(receipt.scheduled_date), '2026-11-05 05:43:00')
        self.assertEqual(receipt.fruit_fundo_id, fundo)
        self.assertFalse(receipt.step_fruit_palletized)
        lines = receipt.fruit_tag_line_ids
        self.assertEqual(lines.variety_id, varieties)
        self.assertEqual(lines.mapped('step_fruit_palletized'), ['yes', 'no'])
        self.assertEqual(sum(lines.mapped('quantity')), 30)
        self.assertEqual(sum(lines.mapped('kilos')), 61.5)
        self.assertFalse(lines.package_id)
        self.assertFalse(self.env['stock.quant'].search_count([('product_id', '=', product.id)]))
        with self.assertRaises(UserError), self.cr.savepoint():
            wizard.action_import()
        receipt.button_validate()
        self.assertEqual(receipt.state, 'done')
        self.assertEqual(sum(lines.package_id.quant_ids.mapped('quantity')), 61.5)
        self.assertEqual(lines.package_id.quant_ids.owner_id, producer)
        self.assertEqual(set(lines.package_id.quant_ids.lot_id.mapped('name')), {'QA189-TARJA-1', 'QA189-TARJA-2'})

        template = self.env['step.external.fruit.reception.template'].search([('name', '=', 'QA T193 externo')])
        self.assertEqual(template.columns['peso del packing'], 'kilos')
        self.assertEqual(template.alias_ids.fundo_id, fundo)
        self.assertEqual(template.alias_ids.packaging_id, packaging)
        sheet.cell(2, 1, 'Referencia')
        sheet.cell(2, 2, 'Número de guía')
        sheet.cell(2, 8, 'Recibir de')
        sheet.cell(2, 9, 'Embalaje')
        for index in range(1, 3):
            sheet.cell(index + 2, 1, 'QA193-02')
            sheet.cell(index + 2, 2, 'QA193-GUIA')
            sheet.cell(index + 2, 3, f'QA193-TARJA-{index}')
        second = model.create(dict(defaults, file=attachment(), template_id=template.id))
        second.action_review()
        self.assertEqual(second.column_ids.filtered(lambda line: line.source == 'Referencia').target, 'folio')
        self.assertEqual(second.column_ids.filtered(lambda line: line.source == 'Peso del packing').target, 'kilos')
        self.assertEqual(second.alias_ids.fundo_id, fundo)
        self.assertEqual(second.alias_ids.packaging_id, packaging)
        another = self.env['stock.picking'].browse(second.action_import()['res_id'])
        self.assertEqual(another.step_external_reception_folio, 'QA193-02')
        self.assertEqual(another.fruit_guide_number, 'QA193-GUIA')
        self.assertEqual(another.fruit_tag_line_ids.packaging_id, packaging)
        self.assertEqual(another.state, 'draft')
