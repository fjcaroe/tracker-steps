# -*- coding: utf-8 -*-
"""Nombre compuesto de Horas Máquina con el segmento OT_BPA."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMachineryBpaNaming(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Usage = cls.env["step.hrs.machinery"]
        cls.bpa_order = cls.env["x_aplicacion_foliar"].create({
            "x_name": "BPA prueba nombre",
            "x_studio_nmero_ot_bpa": "10",
            "state": "status1",
            "company_id": cls.company.id,
        })

    def _create(self, **vals):
        values = {"date": "2026-08-28"}
        values.update(vals)
        return self.Usage.create(values)

    def _force_ot_number(self, record, number):
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE step_hrs_machinery SET ot_number = %s WHERE id = %s", (number, record.id)
        )
        record.invalidate_recordset(["ot_number"])
        record._sync_composed_name()
        return record

    # 3. Nombre completo igual al ejemplo funcional del documento
    def test_full_name_matches_functional_example(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self._force_ot_number(usage, "125")
        self.assertEqual(usage.name, "125 28/08/2026 OT W35 – OT_BPA 10")

    # Sin Orden de trabajo, pero con Folio BPA: sin guion huérfano
    def test_name_without_work_order_keeps_bpa_segment(self):
        usage = self._create(bpa_order_id=self.bpa_order.id)
        self._force_ot_number(usage, "125")
        self.assertEqual(usage.name, "125 28/08/2026 OT_BPA 10")
        self.assertNotIn("–", usage.name)

    # 6. Cambio de Folio BPA antes del costeo
    def test_bpa_change_recomposes_name(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self._force_ot_number(usage, "125")
        other = self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA prueba alterna",
            "x_studio_nmero_ot_bpa": "11",
            "state": "status1",
            "company_id": self.company.id,
        })
        usage.write({"bpa_order_id": other.id})
        self.assertEqual(usage.name, "125 28/08/2026 OT W35 – OT_BPA 11")

    def test_bpa_does_not_overwrite_work_order(self):
        """La OT-BPA no debe pisar la Orden de Trabajo: son datos distintos."""
        usage = self._create(folio="W35")
        usage.bpa_order_id = self.bpa_order
        usage._onchange_bpa_order_id()
        self.assertEqual(usage.folio, "W35")

    def test_name_falls_back_to_reference_without_bpa_number(self):
        order = self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA202600099", "state": "status1", "company_id": self.company.id,
        })
        usage = self._create(bpa_order_id=order.id)
        self._force_ot_number(usage, "126")
        self.assertEqual(usage.name, "126 28/08/2026 OT_BPA BPA202600099")

    # 14. Dominio BPA: sólo órdenes ingresadas y de la empresa correcta
    def test_only_entered_bpa_orders_are_allowed(self):
        approved = self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA costeada", "x_studio_nmero_ot_bpa": "12",
            "state": "status3", "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError):
            self._create(bpa_order_id=approved.id)

    def test_bpa_order_from_another_company_is_rejected(self):
        other_company = self.env["res.company"].create({"name": "BPA Otra Empresa SpA"})
        foreign = self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA ajena", "x_studio_nmero_ot_bpa": "13",
            "state": "status1", "company_id": other_company.id,
        })
        with self.assertRaises(Exception):
            self._create(bpa_order_id=foreign.id)

    # ------------------------------------------------------------------
    # Objetivo 3: el Folio BPA nunca queda desactualizado
    # ------------------------------------------------------------------
    def test_bpa_number_change_updates_draft_usage(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self._force_ot_number(usage, "125")
        self.assertEqual(usage.name, "125 28/08/2026 OT W35 – OT_BPA 10")
        self.bpa_order.write({"x_studio_nmero_ot_bpa": "77"})
        self.assertEqual(usage.bpa_folio, "77")
        self.assertEqual(usage.name, "125 28/08/2026 OT W35 – OT_BPA 77")

    def test_bpa_reference_change_updates_usage_without_number(self):
        order = self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA202600100", "state": "status1", "company_id": self.company.id,
        })
        usage = self._create(bpa_order_id=order.id)
        self._force_ot_number(usage, "130")
        self.assertEqual(usage.name, "130 28/08/2026 OT_BPA BPA202600100")
        order.write({"x_name": "BPA202600101"})
        self.assertEqual(usage.bpa_folio, "BPA202600101")
        self.assertEqual(usage.name, "130 28/08/2026 OT_BPA BPA202600101")

    def test_costed_usage_keeps_its_name_when_bpa_changes(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self._force_ot_number(usage, "125")
        usage.write({"state": "costed"})
        frozen = usage.name
        self.bpa_order.write({"x_studio_nmero_ot_bpa": "99"})
        self.assertEqual(usage.name, frozen, "Un registro costeado conserva su identidad.")
        self.assertEqual(usage.bpa_folio, "99",
                         "El dato operacional sí se refresca, sólo el nombre queda congelado.")

    def test_bpa_folio_is_never_stale_in_database(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self.bpa_order.write({"x_studio_nmero_ot_bpa": "55"})
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT bpa_folio, name FROM step_hrs_machinery WHERE id = %s", (usage.id,))
        stored_folio, stored_name = self.env.cr.fetchone()
        self.assertEqual(stored_folio, "55")
        self.assertIn("OT_BPA 55", stored_name)

    def test_mass_write_over_several_bpa_orders(self):
        second = self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA masiva", "x_studio_nmero_ot_bpa": "20",
            "state": "status1", "company_id": self.company.id,
        })
        first_usage = self._create(folio="W40", bpa_order_id=self.bpa_order.id)
        second_usage = self._create(folio="W41", bpa_order_id=second.id)
        (self.bpa_order | second).write({"x_studio_nmero_ot_bpa": "500"})
        self.assertEqual(first_usage.bpa_folio, "500")
        self.assertEqual(second_usage.bpa_folio, "500")
        self.assertTrue(first_usage.name.endswith("OT W40 – OT_BPA 500"))
        self.assertTrue(second_usage.name.endswith("OT W41 – OT_BPA 500"))

    def test_no_recursion_and_no_useless_writes(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self.env.flush_all()
        before = usage.write_date
        # Escribir un campo que no participa del nombre no debe tocar la Hora Máquina.
        self.bpa_order.write({"x_studio_total_hectreas": 12.5})
        self.env.flush_all()
        usage.invalidate_recordset()
        self.assertEqual(usage.write_date, before,
                         "Sin cambio de folio no debe haber escritura en Horas Máquina.")
        # Reescribir el mismo folio tampoco debe alterar el nombre ni recursar.
        name_before = usage.name
        self.bpa_order.write({"x_studio_nmero_ot_bpa": self.bpa_order.x_studio_nmero_ot_bpa})
        self.env.flush_all()
        self.assertEqual(usage.name, name_before)

    def test_search_reaches_bpa_folio(self):
        usage = self._create(folio="W35", bpa_order_id=self.bpa_order.id)
        self.assertIn("bpa_folio", self.Usage._rec_names_search)
        found = self.Usage.name_search(usage.bpa_folio)
        self.assertIn(usage.id, [item[0] for item in found])
