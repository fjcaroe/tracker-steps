import io
from openpyxl import load_workbook
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from .test_sag import SagCase


@tagged('post_install', '-at_install', 'step_packing_sag')
class SagLotCase(SagCase):
    def _multi_lot(self):
        initial, shipment = self._closed()
        first = initial.package_ids
        initial.unlink()
        self.producer = self.env['res.partner'].create({'name': 'Segundo productor QA T93'})
        city = self.env['res.city'].create({'name': 'Segunda comuna QA', 'country_id': self.env.ref('base.cl').id, 'step_sag_province_name': 'Segunda provincia QA'})
        self.fundo = self.env['step.fundo'].create({'name': 'Segundo fundo QA', 'partner_id': self.producer.id, 'step_sag_city_id': city.id})
        incoming = self._tag('T93-C2', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        self._stock(self.raw, 100, incoming)
        second = self._tag('T93-E2', 'E', self.finished, 100, 20, 'export')
        production = self.env['step.packing.production'].create({'raw_product_id': self.raw.id,
            'fruit_grower_id': self.producer.id, 'fruit_species_id': self.species.id,
            'fruit_variety_id': self.variety.id, 'required_inspection': 'sag',
            'step_packing_input_tag_ids': [(6, 0, incoming.ids)], 'step_packing_output_tag_ids': [(6, 0, second.ids)]})
        self._stock(self.carton, 20)
        production.action_step_packing_validate(); production.action_prepare_materials()
        production.action_approve_materials(); production.action_step_packing_close()
        lot = self.env['step.packing.inspection'].create({'name': 'LOTE SAG QA T93', 'kind': 'sag',
            'sag_species_id': self.species.id, 'sag_fruit_type': 'conventional',
            'inspector_id': self.producer.id, 'package_ids': [(6, 0, (first | second).ids)]})
        return lot, shipment

    def _approved_multi(self):
        lot, shipment = self._multi_lot()
        self.species.sag_code = '10310800'
        plant = self.env['res.partner'].create({'name': 'Establecimiento QA', 'step_sag_plant_number': '3'})
        lot.sag_country_id = self.env.ref('base.us')
        lot.sag_country_id.step_sag_code = '218'
        self._prepare(lot)
        self._evidence(lot)
        lot.write({'sag_packing_id': plant.id, 'sag_sif_reference': '00010', 'sag_export_sequence': '00010',
            'sag_dispatch_sheet_reference': 'PLANILLA-QA-001', 'date': '2010-06-11'})
        for index, tag in enumerate(lot.package_ids.sorted('name'), 38):
            tag.step_sag_folio = str(index)
        lot.action_approve()
        return lot, shipment

    def test_multi_ot_scanner_and_approval_covers_all_outputs(self):
        lot, shipment = self._multi_lot()
        self.assertFalse(lot.production_id)
        self.assertEqual(len(lot.sag_production_ids), 2)
        self.assertEqual(len(lot.package_ids.step_producer_id), 2)
        tags = lot.package_ids
        lot.package_ids = tags[:1]
        lot.sag_scan = tags[1].name
        lot._onchange_sag_scan()
        self.assertEqual(lot.package_ids, tags)
        self.assertFalse(lot.sag_scan)
        lot.sag_scan = tags[1].name
        lot._onchange_sag_scan()
        self.assertEqual(len(lot.package_ids), 2)
        self._prepare(lot); self._evidence(lot)
        lot.action_approve()
        shipment.tag_ids = tags
        shipment._check_tag_load()

    def test_filters_reject_organic_other_variety_no_stock_and_duplicates(self):
        lot, shipment = self._multi_lot()
        for values in [{'sag_fruit_type': 'organic'}, {'sag_species_id': self.env['step.especie'].create({'name': 'Otra especie QA', 'type_especie': 'frutal', 'group_especie': 'fruta_h'}).id}]:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                lot.write(values)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lot.copy({'name': 'Duplicado QA'})
        tag = self._tag('T93-SIN-STOCK', 'E', self.finished, 50, 10, 'export')
        tag.action_step_validate_tag()
        lot.sag_scan = tag.name
        with self.assertRaises(UserError):
            lot._onchange_sag_scan()
        lot.sag_scan = False
        other = self.variety.copy({'name':'Otra variedad QA', 'cod_variedad':'T93OTRA'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lot.sag_variety_ids = other
        shipment.write({'season_id':self.season.id,'species_id':self.species.id,'receiver_id':self.producer.id,
            'line_ids':[(0,0,{'product_id':self.finished.id,'pallet_qty':2,'boxes_per_pallet':20,'kg_per_box':5})]})
        plan = self.env['step.export.dispatch.order'].create({'name':'Instructivo QA T93','shipment_id':shipment.id})
        plan.action_import_shipment_load()
        lot.write({'sag_instruction_id':plan.id,'sag_receiver_id':self.producer.id,'sag_country_id':self.env.ref('base.us').id})
        self.assertEqual(lot.package_ids & lot._sag_candidates(), lot.package_ids)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lot.sag_receiver_id = self.company.partner_id
        plan.load_line_ids.pallet_qty = 1
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lot._check_packages()

    def test_five_annex5_formats_match_official_widths(self):
        lot, shipment = self._approved_multi()
        name, data = lot._sag_flat_file()
        self.assertEqual(name, '00300010.INS')
        self.assertEqual(data, b'00010000310310800218000201006110002\r\n00000000380020\r\n00000000390020\r\n&&\r\n\r\n')
        for service, ext, header_length, row_length in [('service_interplant','INT',13,33), ('service_repack','REP',8,39), ('service_cancel','DET',13,10), ('service_dispatch','DES',19,22)]:
            doc = self.env['step.packing.inspection'].create({'name':'QA '+ext, 'kind':'sag',
                'sag_service_id': self.env.ref('step_packing_sag.'+service).id, 'sag_country_id': lot.sag_country_id.id,
                'sag_species_id': self.species.id, 'sag_packing_id':lot.sag_packing_id.id,
                'sag_export_sequence':'00011', 'sag_dispatch_date':'2010-06-12',
                'inspector_id':self.producer.id, 'package_ids':[(6,0,lot.package_ids.ids)]})
            filename, raw = doc._sag_flat_file()
            lines = raw.decode('ascii').split('\r\n')
            self.assertTrue(filename.endswith('.'+ext)); self.assertEqual(len(lines[0]), header_length)
            self.assertEqual([len(r) for r in lines[1:3]], [row_length,row_length])
            if ext == 'REP':
                doc.sag_repack_operation = 'E'
                self.assertEqual(len(doc._sag_flat_file()[1].decode('ascii').split('\r\n')[1]),16)
        draft = lot.copy({'sag_sif_reference':'00012','sag_export_sequence':'99'})
        self.assertEqual(draft._sag_flat_file()[0], '00300012.INS')
        self.assertEqual(draft.state, 'draft')
        lot.package_ids[:1].step_sag_folio = '12345678901'
        with self.assertRaises(UserError):
            lot._sag_flat_file()

    def test_annex_workbook_pdf_and_missing_origin(self):
        lot, shipment = self._approved_multi()
        rows = lot._sag_annex_rows()
        self.assertEqual(len(rows),2); self.assertNotEqual(rows[0][4],rows[1][4])
        book = load_workbook(io.BytesIO(lot._sag_annex_xlsx()), data_only=True)
        sheet = book.active
        self.assertIn('PLANILLA-QA-001',sheet['A2'].value)
        self.assertEqual(sheet['F7'].value,40)
        pdf, _ = self.env['ir.actions.report'].with_context(force_report_rendering=True)._render_qweb_pdf('step_packing_sag.report_dispatch_annex',res_ids=lot.ids)
        self.assertTrue(pdf.startswith(b'%PDF'))
        lot.package_ids[:1].fundo_id.step_sag_city_id.step_sag_province_name = False
        with self.assertRaises(UserError):
            lot._sag_annex_xlsx()
