import base64
from io import BytesIO

from openpyxl import Workbook

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class ExternalReceiptCase(TransactionCase):
    def test_review_identifies_receipt_header_column_and_excel_rows(self):
        wizard = self.env['step.external.fruit.reception.import']
        first = {'guide': '1058', 'scheduled': '2026-11-11 05:53:00', 'especie': 1,
                 'fundo': 10, 'fruit_type': 'conventional', 'classification': 'psj',
                 'number': 13, 'gassed': 'yes'}
        same_origin = dict(first, number=14, gassed='no')
        wizard._check_receipt_header('63', [first, same_origin])
        with self.assertRaises(UserError) as caught:
            wizard._check_receipt_header('63', [first, dict(same_origin, guide='1059')])
        for detail in ('63', '13', '14', 'guía'):
            self.assertIn(detail, str(caught.exception).lower())

    def test_process_list_totals_from_tags_and_existing_operations(self):
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        picking_model = self.env['stock.picking']
        defaults = {
            'picking_type_id': wh.in_type_id.id, 'location_id': wh.in_type_id.default_location_src_id.id,
            'location_dest_id': wh.lot_stock_id.id, 'step_fruit_reception_kind': 'process',
        }
        with_tags, with_operations, empty = picking_model.create([defaults.copy() for _ in range(3)])
        kg = self.env.ref('uom.product_uom_kgm')
        products = self.env['product.product'].create([
            {'name': name, 'is_storable': True, 'uom_id': kg.id, 'uom_po_id': kg.id}
            for name in ('QA197 arándano', 'QA197 frambuesa')])
        packagings = self.env['product.packaging'].create([
            {'name': name, 'product_id': product.id, 'qty': 10}
            for name, product in zip(('QA197 caja', 'QA197 bandeja'), products)])
        move_values = {
            'name': 'QA197 operación', 'product_id': products[0].id, 'product_uom': kg.id,
            'product_packaging_id': packagings[0].id, 'product_uom_qty': 70,
            'location_id': wh.in_type_id.default_location_src_id.id, 'location_dest_id': wh.lot_stock_id.id,
            'step_fruit_manual_container_qty': 7,
        }
        self.env['stock.move'].create([
            dict(move_values, picking_id=picking.id) for picking in (with_tags, with_operations)])
        self.env['step.packing.picking.tag.line'].create([
            {'picking_id': with_tags.id, 'tag_number': 'QA197-%s' % i, 'product_id': product.id,
             'packaging_id': packaging.id, 'quantity': containers, 'kilos': kilos}
            for i, (product, packaging, containers, kilos) in enumerate(
                zip(products, packagings, (2, 3), (40.0, 42.5)), start=1)])
        columns = [
            'step_reception_product_ids', 'step_reception_packaging_ids', 'step_reception_container_qty',
            'step_reception_net_kg', 'step_reception_avg_kg',
        ]
        rows = {row['id']: row for row in (with_tags | with_operations | empty).read(columns)}
        for picking, expected in (
            (with_tags, (products.ids, packagings.ids, 5, 82.5, 16.5)),
            (with_operations, (products[:1].ids, packagings[:1].ids, 7, 70, 10)),
            (empty, ([], [], 0, 0, 0)),
        ):
            self.assertEqual(tuple(rows[picking.id][field] for field in columns), expected)

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
                10 * index, 20.5 * index, 'GRANEL PROCESO', 'CONVENCIONAL', 'S' if index == 1 else 'N', 'S', 'S' if index == 1 else 'N', 'PSJ'])
        sheet.append(['QA189-01', 'QA189-GUIA', 'QA189-RECHAZADA', '05/11/2026 02:43',
                      species.name, varieties[0].name, 'Cliente', 'Alias externo productor',
                      'Alias externo envase', 5, 10, 'RECHAZADO', 'CONVENCIONAL', 'N', 'S', 'N', 'PSJ'])
        sheet.append([None] * 8 + ['>>Totales', 35, 71.5])
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
        self.assertIn('QA189-RECHAZADA', wizard.review_note)
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
        self.assertFalse(receipt.step_fruit_gassed)
        self.assertEqual(receipt.step_fruit_chilled, 'yes')
        lines = receipt.fruit_tag_line_ids
        self.assertEqual(lines.variety_id, varieties)
        self.assertEqual(lines.mapped('step_fruit_palletized'), ['yes', 'no'])
        self.assertEqual(lines.mapped('step_fruit_gassed'), ['yes', 'no'])
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
        cancelled = another
        cancelled.action_cancel()
        another = self.env['stock.picking'].browse(second.action_import()['res_id'])
        self.assertNotEqual(another, cancelled)
        self.assertEqual(another.step_external_reception_folio, cancelled.step_external_reception_folio)
        another.button_validate()
        old_tags = another.fruit_tag_line_ids.package_id
        action = self.env['step.fruit.receipt.reversal'].create({
            'picking_id': another.id, 'reason': 'QA T206 ajuste de recepción',
        }).action_apply()
        corrected = self.env['stock.picking'].browse(action['res_id'])
        self.assertEqual(another.state, 'done')
        self.assertEqual(another.step_fruit_reversal_id.return_id, another)
        self.assertEqual(another.step_fruit_reversal_id.state, 'done')
        self.assertEqual(another.step_fruit_reversal_id.move_ids.origin_returned_move_id, another.move_ids)
        self.assertEqual(corrected.step_fruit_correction_of_id, another)
        self.assertEqual(corrected.step_external_reception_folio, another.step_external_reception_folio)
        self.assertEqual(corrected.state, 'draft')
        self.assertEqual(set(old_tags.mapped('step_tag_state')), {'void'})
        self.assertFalse(old_tags.quant_ids.filtered('quantity'))
        corrected.button_validate()
        self.assertEqual(corrected.state, 'done')
        fresh_tags = corrected.fruit_tag_line_ids.package_id
        self.assertFalse(old_tags & fresh_tags)
        self.assertEqual(set(old_tags.mapped('name')), set(fresh_tags.mapped('name')))
        self.assertEqual(fresh_tags.quant_ids.owner_id, producer)
        self.assertAlmostEqual(sum(fresh_tags.quant_ids.mapped('quantity')), 61.5)
        with self.assertRaises(UserError):
            another.action_step_reverse_fruit_receipt()

        other_farm = self.env['step.fundo'].create({'name': 'QA T205 Otro fundo', 'partner_id': producer.id})
        for index in range(1, 3):
            sheet.cell(index + 2, 1, 'QA205-OTRO')
            sheet.cell(index + 2, 3, f'QA205-TARJA-{index}')
        separate = model.create(dict(defaults, file=attachment(), template_id=template.id))
        separate.action_review()
        separate.alias_ids.filtered(lambda line: line.kind == 'producer').fundo_id = other_farm
        independent = self.env['stock.picking'].browse(separate.action_import()['res_id'])
        self.assertEqual(independent.fruit_guide_number, corrected.fruit_guide_number)
        self.assertEqual(independent.partner_id, corrected.partner_id)
        self.assertEqual(independent.fruit_fundo_id, other_farm)
        for index, origin in enumerate((fundo, other_farm), start=1):
            sheet.cell(index + 2, 1, 'QA214-MULTI')
            sheet.cell(index + 2, 2, 'QA214-GUIA')
            sheet.cell(index + 2, 3, f'QA214-TARJA-{index}')
            sheet.cell(index + 2, 8, origin.name)
        mixed = model.create(dict(defaults, file=attachment(), template_id=template.id, save_template=False))
        mixed.action_review()
        self.assertIn('2 borradores', mixed.review_note)
        result = mixed.action_import()
        receipts = self.env['stock.picking'].search(result['domain'])
        self.assertEqual(len(receipts), 2)
        self.assertEqual(set(receipts.mapped('step_external_reception_folio')), {'QA214-MULTI'})
        self.assertEqual(set(receipts.fruit_fundo_id.ids), {fundo.id, other_farm.id})
        self.assertEqual(set(receipts.mapped('state')), {'draft'})
        self.assertEqual(sum(receipts.fruit_tag_line_ids.mapped('kilos')), 61.5)
        for receipt in receipts:
            self.assertEqual(len(receipt.fruit_tag_line_ids), 1)
            self.assertEqual(receipt.partner_id, receipt.fruit_fundo_id.partner_id)
        with self.assertRaises(UserError), self.cr.savepoint():
            mixed.action_import()

        process_type = self.env['step.packing.process.type'].create({'name': 'QA T193 Embalaje'})
        process_line = self.env['step.packing.line'].create({'name': 'QA T193 Línea'})
        group = self.env['step.management.caliber.group'].create({'name': 'QA T193 Calibres', 'code': 'T193'})
        caliber = self.env['step.management.fruit.caliber'].create({
            'name': 'QA16+', 'code': 'T193-16', 'group_id': group.id,
        })
        result = self.env['product.product'].create({'name': 'QA T193 Exportación', 'is_storable': True})
        export_packaging = self.env['product.packaging'].create({
            'name': 'QA T193 Caja exportación', 'product_id': result.id, 'qty': 1,
        })
        process_book = Workbook()
        process = process_book.active
        process.append(['FRUTA PROCESADA'])
        process.append(['Nº OP', 'Nº GUÍA', 'Nº LOTE', 'LINEA OP', 'PRODUCTOR', 'ESPECIE', 'VARIEDAD',
                        'CONCEPTO FRUTA', 'KILOS', 'CANT BANDEJAS'])
        process.append(['QA193-OP5', 'QA189-GUIA', 'QA189-TARJA-1', 1, 'Alias externo productor', species.name,
                        varieties[0].name, 'CONVENCIONAL', 20.5, 10])
        process.append(['FRUTA EMBALADA'])
        process.append(['Nº OP', 'FOLIO PALLET', 'F.EMBALAJE', 'LINEA', 'PRODUCTOR', 'ESPECIE', 'VARIEDAD',
                        'CONCEPTO FRUTA', 'EMBALAJE', 'TIPO', 'CANT CAJAS', 'KG EMBALADO', 'KG DE EXPORTACIÓN',
                        'CALIBRE', 'REFERENCIA'])
        process.append(['QA193-OP5', 'T193-PALLET', '2026-11-07', 1, 'Alias externo productor', species.name,
                        varieties[0].name, 'CONVENCIONAL', 'Caja externa', 'PALLET', 8, 18, 18.36,
                        caliber.name, 'Cliente externo'])
        stream = BytesIO()
        process_book.save(stream)
        values = {'packing_id': packing.id, 'line_id': process_line.id, 'process_type_id': process_type.id,
                  'file': base64.b64encode(stream.getvalue()), 'filename': 'process.xlsx', 'template_id': template.id}
        process_wizard = self.env['step.external.packing.process.import'].create(values)
        process_wizard.action_review()
        self.assertFalse(process_wizard.has_commercial)
        process.append(['FRUTA IQF / MERMAS / BAJO CALIBRE'])
        process.append(['TIPO', None, 'Nº OP', 'LINEA', 'ESPECIE', 'VARIEDAD', 'PRODUCTOR',
                        None, 'Nº BANDEJAS', 'KG BRUTO', 'KG NETO'])
        process.append([5, None, 'QA193-OP5', 1, species.name, varieties[0].name, 'Alias externo productor',
                        None, 2, 1.2, 0.75])
        process.append([5, None, 'QA193-OP5', 1, species.name, varieties[0].name, 'Alias externo productor',
                        None, 1, 0.6, 0.25])
        process.append([None] * 6 + ['>>> TOTAL GENERAL:', None, 3, 1.8, 1])
        process.append([None] * 4 + ['RENDIMIENTO', None, 'ITEM', 'DESCRIPCIÓN', None, 'KILOS', '% RENDIMIENTO'])
        process.append([None] * 6 + [4, 'EXCEDENTE DE FRUTA POR DESHIDRATACIÓN', None, 0.36])
        process.append([None] * 6 + [5, 'SOBRE PESO', None, 0.14])
        stream = BytesIO()
        process_book.save(stream)
        values['file'] = base64.b64encode(stream.getvalue())
        process_wizard.file = values['file']
        process_wizard.action_review()
        self.assertTrue(process_wizard.has_commercial)
        process_wizard.mapping_ids.filtered(lambda line: line.kind == 'packaging').packaging_id = export_packaging
        with self.assertRaises(UserError), self.cr.savepoint():
            process_wizard.action_import()
        commercial_product = self.env['product.product'].create({
            'name': 'QA T193 Comercial IQF', 'is_storable': True,
            'uom_id': kg.id, 'uom_po_id': kg.id, 'tracking': 'lot',
        })
        process_wizard.commercial_product_id = commercial_product
        process_wizard.action_import()
        order = self.env['step.packing.production'].search([('step_external_process_folio', '=', 'QA193-OP5'),
                                                            ('packing_partner_id', '=', packing.id)])
        self.assertEqual(order.state, 'created')
        self.assertEqual(order.step_packing_input_tag_ids, lines[0].package_id)
        output = order.step_packing_output_tag_ids.filtered(lambda tag: tag.step_tag_kind == 'E')
        self.assertEqual(output.name, 'T193-PALLET')
        self.assertEqual(output.step_tag_line_ids.boxes, 8)
        self.assertEqual(output.step_tag_line_ids.kilos, 18)
        self.assertEqual(output.step_external_pallet_export_kg, 18.36)
        self.assertFalse(output.quant_ids)
        commercial = order.step_packing_output_tag_ids.filtered(lambda tag: tag.step_tag_kind == 'N')
        self.assertEqual(commercial.name, 'QA193-OP5')
        self.assertEqual(commercial.step_packing_result, 'commercial')
        self.assertEqual(commercial.step_tag_line_ids.product_id, commercial_product)
        self.assertEqual(commercial.step_tag_line_ids.boxes, 3)
        self.assertEqual(commercial.step_tag_line_ids.quantity, 1)
        self.assertEqual(commercial.step_tag_line_ids.kilos, 1)
        self.assertFalse(commercial.quant_ids)
        self.assertEqual(order.step_packing_input_kg, 20.5)
        self.assertEqual(order.step_packing_commercial_kg, 1)
        self.assertEqual(order.step_packing_overweight_kg, 0.5)
        self.assertEqual(order.step_packing_loss_kg, 1)
        another_process = process_wizard.copy(dict(values, commercial_product_id=commercial_product.id))
        another_process.action_review()
        self.assertEqual(another_process.mapping_ids.packaging_id, export_packaging)
        with self.assertRaises(UserError), self.cr.savepoint():
            another_process.action_import()

        company.step_packing_require_contract = False
        self.env['mrp.bom'].create({'product_tmpl_id': result.product_tmpl_id.id})
        order.action_step_packing_validate()
        order.action_prepare_materials()
        order.action_approve_materials()
        order.action_step_packing_close()
        self.assertEqual(output.step_tag_state, 'validated')
        pallet_type = self.env['stock.package.type'].create({
            'name': 'QA T202 pallet 10 cajas', 'step_export_boxes_per_pallet': 10,
        })
        process.delete_rows(7, process.max_row - 6)

        def next_process(folio, boxes, reported_kg, pallet, output_boxes):
            for col, value in {1: folio, 3: lines[1].package_id.name, 7: varieties[1].name,
                               9: reported_kg, 10: boxes}.items():
                process.cell(3, col, value)
            for col, value in {1: folio, 2: pallet, 7: varieties[1].name, 11: output_boxes,
                               12: output_boxes * 2.25, 13: output_boxes * 2.30}.items():
                process.cell(6, col, value)
            file = BytesIO()
            process_book.save(file)
            wizard = self.env['step.external.packing.process.import'].create(dict(
                values, file=base64.b64encode(file.getvalue()), pallet_type_id=pallet_type.id))
            wizard.action_review()
            action = wizard.action_import()
            return self.env[action['res_model']].search(action['domain'])

        source = lines[1].package_id
        with self.assertRaisesRegex(UserError, 'capacidad'), self.cr.savepoint():
            next_process('QA202-OP6', 12, 25, output.name, 3)
        quant = output.quant_ids
        self.env['stock.quant']._update_reserved_quantity(
            quant.product_id, quant.location_id, 1, lot_id=quant.lot_id, package_id=output, strict=True)
        with self.assertRaisesRegex(UserError, 'sin reservas'), self.cr.savepoint():
            next_process('QA202-OP6', 12, 25, output.name, 2)
        self.env['stock.quant']._update_reserved_quantity(
            quant.product_id, quant.location_id, -1, lot_id=quant.lot_id, package_id=output, strict=True)
        self.assertFalse(source.step_external_remainder_id)
        multi = next_process('QA202-OP6', 12, 25, output.name, 2)
        application = multi.step_external_input_ids
        self.assertEqual(application.original_id, source)
        self.assertEqual(application.reported_kg, 25)
        self.assertAlmostEqual(application.kilos, 24.6)
        self.assertAlmostEqual(multi.step_packing_input_kg, 24.6)
        self.assertEqual(source.quant_ids.quantity, 41)
        self.assertEqual(output.step_actual_boxes, 8)
        with self.assertRaisesRegex(UserError, 'Conserve'):
            multi.step_packing_input_tag_ids = [Command.unlink(source.id)]
        multi.action_step_packing_validate()
        self.assertEqual(application.consumed_id, multi.step_packing_input_tag_ids)
        self.assertEqual(source.step_external_remainder_id.step_actual_boxes, 8)
        self.assertAlmostEqual(source.step_external_remainder_id.step_actual_kg, 16.4)
        multi.action_prepare_materials()
        multi.action_approve_materials()
        multi.action_step_packing_close()
        combined = output.step_external_completed_id
        self.assertEqual(combined.name, output.name)
        self.assertEqual(combined.step_tag_state, 'validated')
        self.assertEqual(combined.step_filling, 'complete')
        self.assertEqual(combined.step_actual_boxes, 10)
        self.assertEqual(sum(combined.quant_ids.mapped('quantity')), 10)
        self.assertEqual(combined.step_tag_line_ids.step_external_source_ot_id, order | multi)
        self.assertEqual(combined.step_tag_line_ids.step_external_source_variety_id, varieties)
        self.assertFalse(combined.variedad_id)
        self.assertEqual(order.step_packing_export_kg, 18)
        self.assertEqual(multi.step_packing_export_kg, 4.5)
        self.assertEqual(output.step_tag_state, 'repalletized')
        self.assertEqual(multi.step_packing_output_tag_ids.step_tag_state, 'repalletized')
        self.assertAlmostEqual(source.step_external_remainder_id.quant_ids.quantity, 16.4)
        with self.assertRaisesRegex(UserError, 'cajas disponibles'), self.cr.savepoint():
            next_process('QA202-OP7', 9, 18, 'QA202-NUEVO', 1)
        last = next_process('QA202-OP7', 8, 16, 'QA202-NUEVO', 1)
        self.assertEqual(last.step_packing_input_tag_ids, source.step_external_remainder_id)
        self.assertAlmostEqual(last.step_packing_input_kg, 16.4)
