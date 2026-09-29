import base64
from io import BytesIO

from openpyxl import Workbook

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFruitOperations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.producer = cls.env["res.partner"].create({"name": "Productor T40", "is_productor": True})
        cls.fundo = cls.env["step.fundo"].create({
            "name": "Fundo T40", "partner_id": cls.producer.id,
            "company_id": cls.company.id, "sdp_code": "SDP-T40",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Fruta T40", "default_code": "T40-FRUTA", "is_storable": True,
            "weight": 5.0,
        })
        cls.warehouse = cls.env["stock.warehouse"].search([
            ("company_id", "=", cls.company.id)], limit=1)

    def _package(self, name="T40-TARJA-1", kind="E"):
        return self.env["stock.quant.package"].create({
            "name": name, "is_fruit_tag": True, "step_tag_kind": kind,
            "fundo_id": self.fundo.id, "step_producer_id": self.producer.id,
            "step_tag_line_ids": [(0, 0, {
                "producer_id": self.producer.id, "product_id": self.product.id,
                "quantity": 10, "kilos": 50, "boxes": 10,
            })],
        })

    def test_package_state_and_producer_detail(self):
        package = self._package()
        package.action_step_validate_tag()
        self.assertEqual(package.step_tag_state, "validated")
        self.assertEqual(package.step_composition, "simple")
        self.assertEqual(package.step_actual_kg, 50)
        self.assertEqual(package.step_sdp_code, "SDP-T40")
        with self.cr.savepoint(), self.assertRaises(ValidationError):
            package.step_tag_state = "processed"  # estado exclusivo de tarja C

    def test_producer_container_location_reused(self):
        first = self.producer.action_step_container_location()["res_id"]
        second = self.producer.action_step_container_location()["res_id"]
        self.assertEqual(first, second)
        location = self.env["stock.location"].browse(first)
        self.assertEqual(location.usage, "internal")
        self.assertEqual(location.step_producer_id, self.producer)

    def test_excel_import_creates_tags_without_validating_stock(self):
        picking = self.env["stock.picking"].create({
            "partner_id": self.producer.id,
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.warehouse.in_type_id.default_location_src_id.id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "step_fruit_reception_kind": "packed",
            "fruit_fundo_id": self.fundo.id,
            "fruit_species_id": self.env["step.especie"].create({
                "name": "Cerezas T40", "type_especie": "frutal", "group_especie": "baya",
            }).id,
        })
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Tarja", "Producto", "Cantidad", "Kilos", "Cajas", "Peso bruto", "Destare"])
        sheet.append(["T40-IMPORT-1", "T40-FRUTA", 10, 50, 10, 55, 5])
        data = BytesIO()
        workbook.save(data)
        wizard = self.env["step.fruit.reception.import"].create({
            "picking_id": picking.id, "filename": "tarjas.xlsx",
            "file": base64.b64encode(data.getvalue()),
        })
        wizard.action_import()
        self.assertEqual(len(picking.fruit_tag_line_ids), 1)
        package = picking.fruit_tag_line_ids.package_id
        self.assertEqual(package.step_tag_kind, "E")
        self.assertEqual(package.step_tag_state, "created")
        with self.assertRaises(ValidationError):
            picking._check_step_fruit_reception()  # aún falta asignar a operaciones de stock

    def test_reception_validates_stock_and_tag_detail(self):
        package = self.env["stock.quant.package"].create({
            "name": "T40-RECEPCION-1", "is_fruit_tag": True,
            "step_tag_kind": "E",
        })
        species = self.env["step.especie"].create({
            "name": "Cerezas recepción T40", "type_especie": "frutal", "group_especie": "baya",
        })
        season = self.env["step.temporada"].create({"name": "Temporada recepción T40"})
        picking = self.env["stock.picking"].create({
            "partner_id": self.producer.id,
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.warehouse.in_type_id.default_location_src_id.id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "step_fruit_reception_kind": "packed",
            "fruit_fundo_id": self.fundo.id, "fruit_species_id": species.id,
            "fruit_season_id": season.id,
            "step_fruit_gross_kg": 55, "step_fruit_container_tare_kg": 5,
            "fruit_tag_line_ids": [(0, 0, {
                "tag_number": package.name, "package_id": package.id,
                "product_id": self.product.id, "quantity": 10,
                "kilos": 50, "box_count": 10,
            })],
        })
        move = self.env["stock.move"].create({
            "name": "Fruta T40", "picking_id": picking.id,
            "product_id": self.product.id, "product_uom_qty": 10,
            "product_uom": self.product.uom_id.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
        })
        picking.action_confirm()
        move.move_line_ids.write({"quantity": 10, "result_package_id": package.id})
        self.assertTrue(move.move_line_ids)
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(package.step_tag_state, "validated")
        self.assertEqual(package.step_producer_id, self.producer)
        self.assertEqual(package.step_export_season_id, season)
        self.assertEqual(package.especie_id, species)
        self.assertEqual(package.step_actual_kg, 50)
        self.assertEqual(package.quant_ids.product_id, self.product)
