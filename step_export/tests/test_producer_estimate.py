# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestProducerEstimate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.producer = cls.env["res.partner"].create({"name": "Productor T35", "is_productor": True})
        cls.packing = cls.env["res.partner"].create({"name": "Packing T35", "step_export_packing": True})
        cls.fundo = cls.env["step.fundo"].create({"name": "Fundo T35", "partner_id": cls.producer.id})
        cls.season = cls.env["step.temporada"].create({"name": "Temporada T35 EP"})
        cls.species = cls.env["step.especie"].create({
            "name": "Cereza T35", "type_especie": "frutal", "group_especie": "seco",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Fruta T35", "is_fruta": True, "grupo_labor": "pack",
        })

    def _estimate(self, **overrides):
        values = {
            "name": "Cereza estimada", "producer_id": self.producer.id,
            "fundo_id": self.fundo.id, "packing_partner_id": self.packing.id,
            "season_id": self.season.id,
            "delivery_start": date(2026, 11, 2), "delivery_end": date(2026, 11, 15),
            "estimate_line_ids": [(0, 0, {
                "delivery_kind": "process", "species_id": self.species.id,
                "product_id": self.product.id, "export_kg": 100000,
                "export_percentage": 0.8, "kg_per_box": 9, "boxes_per_package": 35,
                "week_line_ids": [(0, 0, {"week_start": date(2026, 11, 2), "export_kg": 40000}),
                                  (0, 0, {"week_start": date(2026, 11, 9), "export_kg": 60000})],
            })],
        }
        values.update(overrides)
        return self.env["step.export.estimate"].create(values)

    def test_process_formulas_and_weekly_distribution(self):
        estimate = self._estimate()
        line = estimate.estimate_line_ids
        self.assertEqual(estimate.export_kg_total, 100000)
        self.assertAlmostEqual(line.process_kg, 125000)
        self.assertAlmostEqual(line.harvest_box_qty, 125000 / 9)
        self.assertAlmostEqual(line.bin_qty, 125000 / 9 / 35)
        estimate.action_validate_estimate()
        estimate.action_activate_estimate()
        self.assertEqual(estimate.state, "current")

    def test_version_is_editable_and_previous_version_immutable(self):
        old = self._estimate()
        old.action_validate_estimate()
        old.action_activate_estimate()
        new = self.env["step.export.estimate"].browse(old.action_new_estimate_version()["res_id"])
        self.assertEqual(new.version_number, 2)
        self.assertEqual(new.export_kg_total, old.export_kg_total)
        new.estimate_line_ids.export_kg = 120000
        weeks = new.estimate_line_ids.week_line_ids.sorted("week_start")
        weeks[0].export_kg = 50000
        weeks[1].export_kg = 70000
        new.action_validate_estimate()
        new.action_activate_estimate()
        self.assertEqual(old.state, "replaced")
        self.assertEqual(new.state, "current")
        with self.assertRaises(UserError):
            old.estimate_line_ids.write({"export_kg": 100})

    def test_all_export_kilos_must_be_distributed(self):
        estimate = self._estimate()
        estimate.estimate_line_ids.week_line_ids[0].export_kg = 39999
        with self.assertRaises(ValidationError):
            estimate.action_validate_estimate()
