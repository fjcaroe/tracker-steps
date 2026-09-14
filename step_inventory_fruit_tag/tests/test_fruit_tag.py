# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_inventory_fruit_tag")
class TestFruitTag(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.location = cls.env.ref(
            "step_inventory_fruit_tag.stock_location_bodega_fruta")
        cls.partner = cls.env["res.partner"].create({"name": "Productor Test"})
        cls.fundo = cls.env["step.fundo"].create({
            "name": "Fundo Test",
            "partner_id": cls.partner.id,
            "company_id": cls.company.id,
        })
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.product = cls.env["product.template"].create({
            "name": "Arándano test",
            "is_storable": True,
            "weight": 5.0,
            "uom_id": cls.uom_kg.id,
        }).product_variant_id

    def test_real_warehouses_seeded(self):
        """El ticket 22 quedó bloqueado hasta que el cliente confirmara los
        nombres reales de bodega; esto verifica que la semilla los use tal
        cual los dio (respuesta del 14-09-2026)."""
        names = {"Bodega Insumos", "Bodega Fruta", "Bodega BPA", "Bodega Máquina"}
        locations = self.env["stock.location"].search([("name", "in", list(names))])
        self.assertEqual(set(locations.mapped("name")), names)
        self.assertTrue(all(loc.usage == "internal" for loc in locations))

    def test_fundo_onchange_sets_owner(self):
        package = self.env["stock.quant.package"].new({"fundo_id": self.fundo.id})
        package._onchange_fundo_id()
        self.assertEqual(package.owner_id, self.partner)

    def test_kilos_total_computed_from_quants(self):
        package = self.env["stock.quant.package"].create({"name": "TARJA-TEST-0001"})
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.location, 10.0, package_id=package)
        self.assertAlmostEqual(package.kilos_total, 50.0)

    def test_stock_move_kilos(self):
        other_location = self.env.ref(
            "step_inventory_fruit_tag.stock_location_bodega_insumos")
        move = self.env["stock.move"].create({
            "name": "Test move",
            "product_id": self.product.id,
            "product_uom_qty": 4.0,
            "product_uom": self.product.uom_id.id,
            "location_id": other_location.id,
            "location_dest_id": self.location.id,
        })
        self.assertAlmostEqual(move.fruit_tag_kilos, 20.0)

    def test_fruit_quality_seed_data(self):
        codes = self.env["step.management.fruit.quality"].search([]).mapped("code")
        for expected in ("A", "B", "C1", "J1"):
            self.assertIn(expected, codes)
