# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestExportSalesProgram(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Recibidor de prueba", "step_export_receiver": True,
        })
        cls.season = cls.env["step.temporada"].create({"name": "Temporada T35"})
        cls.species = cls.env["step.especie"].create({
            "name": "Cereza", "type_especie": "frutal", "group_especie": "seco",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Caja 5 kg", "is_fruta": True, "step_export_enabled": True,
            "grupo_labor": "pack",
        })
        cls.package_type = cls.env["stock.package.type"].create({"name": "Pallet T35"})

    def _program(self, **overrides):
        values = {
            "name": "Cerezas 5 kg", "partner_id": self.partner.id,
            "season_id": self.season.id, "species_id": self.species.id,
            "product_id": self.product.id, "package_type_id": self.package_type.id,
            "date_start": date(2026, 11, 2), "date_end": date(2026, 11, 15),
            "pallets_per_container": 20, "boxes_per_pallet": 184,
            "kg_per_box": 5, "rate_to_usd": 1.2,
            "line_ids": [(0, 0, {"week_start": date(2026, 11, 2),
                                  "container_qty": 1, "price_per_kg": 7}),
                         (0, 0, {"week_start": date(2026, 11, 9),
                                  "container_qty": 2, "price_per_kg": 6})],
        }
        values.update(overrides)
        return self.env["step.export.sales.program"].create(values)

    def test_weekly_and_total_quantities(self):
        program = self._program()
        self.assertEqual(program.container_qty, 3)
        self.assertEqual(program.pallet_qty, 60)
        self.assertEqual(program.box_qty, 11040)
        self.assertEqual(program.kg_qty, 55200)
        self.assertEqual(program.amount_currency, 18400 * 7 + 36800 * 6)
        self.assertAlmostEqual(program.amount_usd, program.amount_currency * 1.2)

    def test_version_replaces_current_and_preserves_history(self):
        program = self._program()
        program.action_validate()
        program.action_activate()
        action = program.action_new_version()
        new = self.env["step.export.sales.program"].browse(action["res_id"])
        self.assertEqual((new.series_code, new.version), (program.series_code, 2))
        self.assertEqual(new.state, "created")
        self.assertEqual(new.kg_qty, program.kg_qty)
        new.line_ids[0].container_qty = 3
        new.action_validate()
        new.action_activate()
        self.assertEqual(program.state, "replaced")
        self.assertEqual(new.state, "current")
        self.assertEqual(program.container_qty, 3)
        with self.assertRaises(UserError):
            program.write({"name": "Alterado"})
        with self.assertRaises(UserError):
            new.line_ids[0].write({"container_qty": 8})

    def test_rejects_invalid_week_and_incomplete_packing(self):
        with self.assertRaises(ValidationError):
            self._program(line_ids=[(0, 0, {"week_start": date(2026, 11, 3),
                                           "container_qty": 1, "price_per_kg": 5})])
        incomplete = self._program(kg_per_box=0)
        with self.assertRaises(ValidationError):
            incomplete.action_validate()
