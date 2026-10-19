from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from lxml import etree
from ..models.inspection import CHECKS


@tagged('post_install', '-at_install', 'step_packing_sag')
class SagCase(TransactionCase):
    def _fixture(self):
        self.company = self.env.company
        self.season = self.env['step.temporada'].create({'name':'Temporada QA T93'})
        self.warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.company.id)], limit=1)
        self.location = self.warehouse.lot_stock_id
        self.producer = self.env["res.partner"].create({"name": "Productor Packing T41"})
        self.species = self.env["step.especie"].create({
            "name": "Cereza Packing T41", "type_especie": "frutal", "group_especie": "fruta_h"})
        self.variety_group = self.env["step.grupo.variedad"].create({
            "name": "Grupo T41", "especie_id": self.species.id})
        self.variety = self.env["step.variedad"].create({
            "name": "Santina T41", "cod_variedad": "T41S", "especie_id": self.species.id,
            "grupo_variedad_id": self.variety_group.id})
        self.raw = self.env["product.product"].create({
            "name": "Fruta granel T41", "is_storable": True, "weight": 1.0, "grupo_labor": "pack"})
        self.finished = self.env["product.product"].create({
            "name": "Caja exportación T41", "default_code": "T41-EXPORT", "is_storable": True, "weight": 5.0, "grupo_labor": "pack"})
        self.national = self.env["product.product"].create({
            "name": "Fruta nacional T41", "is_storable": True, "weight": 1.0, "grupo_labor": "pack"})
        self.city = self.env['res.city'].create({'name':'Comuna QA', 'country_id':self.env.ref('base.cl').id, 'step_sag_province_name':'Provincia QA'})
        self.fundo = self.env['step.fundo'].create({'name':'Fundo QA', 'partner_id':self.producer.id, 'step_sag_city_id':self.city.id})
        self.carton = self.env["product.product"].create({
            "name": "Cartón T41", "is_storable": True, "grupo_labor": "pack"})

    def _order(self, forbidden=False):
        return self.env["step.packing.order"].create({
            "week_start": "2026-11-09", "week_end": "2026-11-15",
            "forbidden_producer_ids": [(6, 0, self.producer.ids)] if forbidden else [],
            "line_ids": [(0, 0, {
                "product_id": self.finished.id, "species_id": self.species.id,
                "variety_id": self.variety.id, "boxes": 100, "kilos": 500,
            })],
        })

    def _tag(self, name, kind, product, kilos, boxes, result=False):
        return self.env["stock.quant.package"].create({
            "name": name, "is_fruit_tag": True, "step_tag_kind": kind, "fruit_type": "conventional", "fundo_id": self.fundo.id, "step_export_season_id": self.season.id,
            "step_packing_result": result, "step_producer_id": self.producer.id,
            "especie_id": self.species.id, "variedad_id": self.variety.id,
            "step_tag_line_ids": [(0, 0, {
                "producer_id": self.producer.id, "product_id": product.id,
                "quantity": boxes, "boxes": boxes, "kilos": kilos,
            })],
        })

    def _stock(self, product, qty, package=False):
        self.env["stock.quant"]._update_available_quantity(product, self.location, qty, package_id=package or None)

    def _production(self, order, inputs, outputs, bom=False):
        vals = {
            "product_id": self.finished.id, "product_qty": 100,
            "product_uom_id": self.finished.uom_id.id,
            "step_packing_order_id": order.id,
            "step_packing_input_tag_ids": [(6, 0, inputs.ids)],
            "step_packing_output_tag_ids": [(6, 0, outputs.ids)],
        }
        if bom:
            vals["bom_id"] = bom.id
        return self.env["step.packing.production"].create(vals)

    def _closed(self):
        self._fixture()
        incoming = self._tag('T92-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        self._stock(self.raw, 100, incoming)
        production = self.env['step.packing.production'].create({
            'raw_product_id': self.raw.id, 'fruit_grower_id': self.producer.id,
            'fruit_species_id': self.species.id, 'fruit_variety_id': self.variety.id,
            'required_inspection': 'sag', 'step_packing_input_tag_ids': [(6, 0, incoming.ids)]})
        tag = self._tag('T92-E', 'E', self.finished, 100, 20, 'export')
        production.step_packing_output_tag_ids = tag
        self.env['mrp.bom'].create({'product_tmpl_id': self.finished.product_tmpl_id.id,
            'product_qty': 1, 'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1})]})
        self._stock(self.carton, 20)
        production.action_step_packing_validate()
        production.action_prepare_materials()
        production.action_approve_materials()
        production.action_step_packing_close()
        self.assertEqual(production.state, 'closed')
        inspection = self.env['step.packing.inspection'].create({
            'name': 'T92 SAG prueba aislada', 'production_id': production.id, 'kind': 'sag',
            'inspector_id': self.producer.id, 'package_ids': [(6, 0, tag.ids)]})
        shipment = self.env['step.export.export'].create({'name': 'T92 prueba aislada',
            'destination_country_id': self.env.ref('base.us').id, 'tag_ids': [(6, 0, tag.ids)]})
        return inspection, shipment

    def _prepare(self, inspection):
        inspection.write(dict.fromkeys(CHECKS, 'yes') | {
            'sag_country_id': self.env.ref('base.us').id, 'sag_counterpart_id': self.producer.id,
            'sag_requirements': 'REQUISITO FICTICIO QA - no usar comercialmente. Consulta 2026-10-18.',
            'sag_treatment': 'none'})
        inspection.action_sag_ready()
        inspection.write({'sag_request_reference': 'QA SOLICITUD SIN VALIDEZ', 'sag_scheduled_at': fields.Datetime.now()})
        inspection.action_sag_requested()

    def _evidence(self, inspection):
        evidence = self.env['ir.attachment'].create({'name': 'RESPALDO FICTICIO QA.txt',
            'type': 'binary', 'raw': b'PRUEBA AISLADA SIN VALIDEZ OFICIAL',
            'res_model': inspection._name, 'res_id': inspection.id})
        inspection.write({'sag_sif_reference': 'QA SIF', 'certificate_reference': 'QA SIN VALIDEZ',
            'sag_evidence_ids': [(6, 0, evidence.ids)], 'sag_sampling_basis': 'QA Anexo 7',
            'sag_sample_count': 2, 'sag_sample_findings': 'QA: unidades identificadas en tarja T92-E, sin hallazgos en prueba.'})

    def test_lifecycle_pending_and_destination_dispatch_gate(self):
        inspection, shipment = self._closed()
        with self.assertRaises(UserError):
            shipment._check_tag_load()
        self._prepare(inspection)
        self.assertEqual(inspection.state, 'draft')
        self._evidence(inspection)
        inspection.write({'sag_laboratory_reference': 'QA MUESTRA', 'observations': 'QA pendiente de resultado externo'})
        inspection.action_sag_pending()
        with self.assertRaises(UserError):
            inspection.write({'sag_phase': 'ready'})
        with self.assertRaises(UserError):
            inspection.action_sag_ready()
        with self.assertRaises(UserError):
            inspection.action_sag_requested()
        with self.assertRaises(UserError):
            inspection.unlink()
        with self.assertRaises(UserError):
            shipment._check_tag_load()
        with self.assertRaises(UserError):
            inspection.action_approve()
        inspection.sag_laboratory_received = True
        inspection.action_approve()
        self.assertEqual(inspection.state, 'approved')
        shipment._check_tag_load()
        with self.assertRaises(UserError):
            inspection.write({'observations': 'Alterar resultado'})
        shipment.destination_country_id = self.env.ref('base.cl')
        with self.assertRaises(UserError):
            shipment._check_tag_load()
        shipment.destination_country_id = self.env.ref('base.us')
        reevaluation = inspection.copy({'name': 'T92 nueva evaluacion'})
        self.assertEqual(reevaluation.state, 'draft')
        self.assertFalse(reevaluation.sag_evidence_ids)
        with self.assertRaises(UserError):
            shipment._check_tag_load()

    def test_required_evidence_sampling_treatment_and_rejection(self):
        inspection, shipment = self._closed()
        with self.assertRaises(UserError):
            inspection.action_sag_ready()
        self._prepare(inspection)
        inspection.certificate_reference = 'QA SIN RESPALDO'
        with self.assertRaises(UserError):
            inspection.action_approve()
        self._evidence(inspection)
        inspection.sag_treatment = 'required'
        with self.assertRaises(UserError):
            inspection.action_approve()
        inspection.sag_treatment = 'done'
        with self.assertRaises(UserError):
            inspection.action_approve()
        inspection.write({'sag_treatment_detail': 'QA tipo/numero/fecha/condiciones', 'sag_sample_count': 0})
        with self.assertRaises(UserError):
            inspection.action_approve()
        inspection.observations = 'QA causal externa de rechazo'
        inspection.action_reject()
        self.assertEqual(inspection.state, 'rejected')
        with self.assertRaises(UserError):
            shipment._check_tag_load()

    def test_access_company_and_validation(self):
        inspection, shipment = self._closed()
        self._prepare(inspection)
        self._evidence(inspection)
        user = new_test_user(self.env, login='t92-stock-user', groups='stock.group_stock_user', company_id=self.company.id)
        with self.assertRaises(UserError):
            inspection.with_user(user).action_approve()
        other = self.env['res.company'].create({'name': 'T92 otra empresa'})
        stranger = new_test_user(self.env, login='t92-other-company', groups='stock.group_stock_manager', company_id=other.id)
        with self.assertRaises(AccessError):
            inspection.with_user(stranger).read(['name'])
        with self.assertRaises(UserError):
            inspection.write({'kind': 'internal'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            inspection.sag_sample_count = -1
        foreign = self.env['ir.attachment'].create({'name': 'Ajeno', 'type': 'binary', 'raw': b'QA', 'res_model': 'res.partner', 'res_id': self.producer.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            inspection.sag_evidence_ids = foreign

    def test_native_internal_and_menu_form(self):
        inspection, shipment = self._closed()
        internal = self.env['step.packing.inspection'].create({'name': 'T92 interna',
            'production_id': inspection.production_id.id, 'kind': 'internal',
            'inspector_id': self.producer.id, 'package_ids': [(6, 0, inspection.package_ids.ids)]})
        self.assertFalse(internal.sag_prototype)
        internal.action_approve()
        self.assertEqual(internal.state, 'approved')
        action = self.env.ref('step_packing_dispatch.sag_action')
        self.assertEqual(action.res_model, 'step.packing.inspection')
        self.assertIn(self.env.ref('step_packing_sag.sag_form'), action.view_ids.view_id)
        menu = self.env.ref('step_packing_dispatch.sag_menu')
        self.assertEqual(menu.parent_id, self.env.ref('step_packing_dispatch.inspections_menu'))
        form = self.env['step.packing.inspection'].get_view(self.env.ref('step_packing_sag.sag_form').id, 'form')['arch']
        lot_field = etree.fromstring(form).xpath("//field[@name='package_ids'][@domain]")[0]
        self.assertIn('sag_available_package_ids', lot_field.get('domain'))
        self.assertFalse(etree.fromstring(form).xpath("//field[@name='sag_grower_id']"))
        self.assertIn(inspection.production_id, self.env['step.packing.production'].search([('company_id', 'in', self.env.companies.ids)]))
        for field in ('sag_country_id', 'sag_sampling_basis', 'sag_treatment', 'sag_evidence_ids'):
            self.assertIn(field, form)
