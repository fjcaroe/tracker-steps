# -*- coding: utf-8 -*-
"""Correlativo Número OT y nombre compuesto de Horas Máquina."""

import importlib.util
import os

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.step_machinery.models.step_hrs_machinery import OT_SEQUENCE_CODE


@tagged("post_install", "-at_install")
class TestMachineryOtNaming(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Usage = cls.env["step.hrs.machinery"]

    def _create(self, **vals):
        values = {"date": "2026-08-28"}
        values.update(vals)
        return self.Usage.create(values)

    def _force_ot_number(self, record, number):
        """Fija un Número OT concreto para comparar contra el ejemplo funcional."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE step_hrs_machinery SET ot_number = %s WHERE id = %s", (number, record.id)
        )
        record.invalidate_recordset(["ot_number"])
        record._sync_composed_name()
        return record

    @staticmethod
    def _load_migration():
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations", "18.0.20.0.0", "post-migrate.py",
        )
        spec = importlib.util.spec_from_file_location("step_machinery_post_migrate_20", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # 1. Crear sin enviar name
    def test_create_without_name(self):
        usage = self._create()
        self.assertTrue(usage.ot_number, "El correlativo debe asignarse en el servidor.")
        self.assertTrue(usage.name, "El nombre debe generarse solo al guardar.")
        self.assertNotIn("False", usage.name)
        self.assertNotIn("None", usage.name)
        self.assertNotIn("  ", usage.name)

    # 2. Correlativos consecutivos y sin duplicados
    def test_sequential_ot_numbers(self):
        first, second, third = self._create(), self._create(), self._create()
        numbers = [int(record.ot_number) for record in (first, second, third)]
        self.assertEqual(numbers[1], numbers[0] + 1)
        self.assertEqual(numbers[2], numbers[1] + 1)
        self.assertEqual(len(set(numbers)), 3)

    def test_duplicate_ot_number_is_rejected(self):
        usage = self._create()
        other = self._create()
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "UPDATE step_hrs_machinery SET ot_number = %s WHERE id = %s",
                    (usage.ot_number, other.id),
                )

    # 4. Nombre correcto sin Orden de trabajo (y sin Folio BPA)
    def test_name_without_work_order(self):
        usage = self._force_ot_number(self._create(), "125")
        self.assertEqual(usage.name, "125 28/08/2026")

    # 5. Nombre correcto sin Folio BPA
    def test_name_without_bpa(self):
        usage = self._force_ot_number(self._create(folio="W35"), "125")
        self.assertEqual(usage.name, "125 28/08/2026 OT W35")

    # 6. Cambio de fecha / orden de trabajo antes del costeo
    def test_name_is_recomposed_before_costing(self):
        usage = self._force_ot_number(self._create(folio="W35"), "125")
        usage.write({"date": "2026-09-01", "folio": "W36"})
        self.assertEqual(usage.name, "125 01/09/2026 OT W36")

    # 7. Identidad estable después de costear o contabilizar
    def test_name_is_frozen_after_costing(self):
        usage = self._force_ot_number(self._create(folio="W35"), "125")
        frozen = usage.name
        usage.write({"state": "costed"})
        usage.write({"folio": "W99", "date": "2026-12-31"})
        self.assertEqual(usage.name, frozen)
        self.assertEqual(usage.folio, "W99", "El dato operacional sí puede corregirse.")

    # 8. Copia con nuevo correlativo
    def test_copy_gets_new_ot_number(self):
        usage = self._create(folio="W35")
        clone = usage.copy()
        self.assertNotEqual(clone.ot_number, usage.ot_number)
        self.assertNotEqual(clone.name, usage.name)
        self.assertFalse(clone.legacy_name)
        self.assertEqual(clone.folio, "W35")

    # 9. Dos empresas sin colisiones
    def test_two_companies_do_not_collide(self):
        other_company = self.env["res.company"].create({"name": "Maquinaria Prueba SpA"})
        first = self._create()
        second = self._create(company_id=other_company.id)
        self.assertNotEqual(first.ot_number, second.ot_number)
        pairs = {
            (first.company_id.id, first.ot_number),
            (second.company_id.id, second.ot_number),
        }
        self.assertEqual(len(pairs), 2)

    def test_company_change_policy(self):
        other_company = self.env["res.company"].create({"name": "Maquinaria Destino SpA"})
        usage = self._create()
        original = usage.ot_number
        usage.write({"company_id": other_company.id})
        self.assertNotEqual(
            usage.ot_number, original, "Al cambiar de empresa se reemite el correlativo."
        )
        usage.write({"state": "costed"})
        with self.assertRaises(UserError):
            usage.write({"company_id": self.company.id})

    # 10. Creación por RPC/API con el contrato que todavía envía name
    def test_legacy_payload_with_name_is_accepted(self):
        usage = self.Usage.create({
            "name": "CARGA-TRACKER-001", "date": "2026-08-28", "folio": "W35",
        })
        self.assertEqual(usage.legacy_name, "CARGA-TRACKER-001")
        self.assertNotEqual(usage.name, "CARGA-TRACKER-001")
        self.assertTrue(usage.name.endswith("OT W35"))

    def test_legacy_payload_cannot_override_on_write(self):
        usage = self._force_ot_number(self._create(folio="W35"), "125")
        usage.write({"name": "NOMBRE-EXTERNO"})
        self.assertEqual(usage.name, "125 28/08/2026 OT W35")
        self.assertEqual(usage.legacy_name, "NOMBRE-EXTERNO")

    def test_supplied_ot_number_is_ignored(self):
        usage = self.Usage.create({"date": "2026-08-28", "ot_number": "999999"})
        self.assertNotEqual(usage.ot_number, "999999")

    # 11. Migración idempotente sobre registros existentes
    def test_migration_is_idempotent(self):
        module = self._load_migration()
        usage = self._create(folio="W35")
        # Simula un registro anterior a la normalización: sin correlativo y con
        # el nombre digitado a mano. El vaciado debe hacerse ya en base de datos.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE step_hrs_machinery SET ot_number = NULL, legacy_name = NULL, name = %s "
            "WHERE id = %s", ("NOMBRE ANTIGUO", usage.id),
        )
        self.env.invalidate_all()

        module._preserve_legacy_names(self.env.cr)
        assigned_first, highest_first = module._assign_ot_numbers(self.env.cr)
        self.env.invalidate_all()
        first_number = usage.ot_number
        self.assertTrue(first_number)
        self.assertEqual(usage.legacy_name, "NOMBRE ANTIGUO")
        self.assertGreaterEqual(assigned_first, 1)

        self.env.flush_all()
        module._preserve_legacy_names(self.env.cr)
        assigned_second, highest_second = module._assign_ot_numbers(self.env.cr)
        self.env.invalidate_all()
        self.assertEqual(assigned_second, 0, "La segunda pasada no debe reasignar correlativos.")
        self.assertEqual(highest_second, highest_first)
        self.assertEqual(usage.ot_number, first_number)
        self.assertEqual(usage.legacy_name, "NOMBRE ANTIGUO")

    def test_sequence_has_no_decorative_prefix(self):
        sequence = self.env["ir.sequence"].sudo().search([("code", "=", OT_SEQUENCE_CODE)], limit=1)
        self.assertTrue(sequence, "Debe existir la secuencia del Número OT.")
        self.assertFalse(sequence.prefix)
        self.assertFalse(sequence.suffix)
        usage = self._create()
        self.assertTrue(usage.ot_number.isdigit(), "El correlativo debe ser un número limpio.")

    # Objetivo 2: las referencias históricas deben seguir siendo encontrables
    def test_search_by_legacy_name(self):
        usage = self._create(folio="W36")
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE step_hrs_machinery SET legacy_name = %s WHERE id = %s",
            ("OT W35", usage.id),
        )
        self.env.invalidate_all()
        self.assertEqual(usage.legacy_name, "OT W35")
        found = self.Usage.search([("legacy_name", "ilike", "OT W35")])
        self.assertIn(usage, found)
        self.assertIn("legacy_name", self.Usage._rec_names_search)
        by_name_search = self.Usage.name_search("OT W35")
        self.assertIn(usage.id, [item[0] for item in by_name_search],
                      "name_search debe alcanzar el nombre histórico.")
        self.assertEqual(usage.name, "%s 28/08/2026 OT W36" % usage.ot_number,
                         "La búsqueda no debe alterar el nombre compuesto.")
        self.assertEqual(usage.legacy_name, "OT W35", "legacy_name no se toca.")

    def test_search_view_domain_covers_legacy_name(self):
        view = self.env.ref("step_machinery.view_step_hrs_machinery_search")
        arch = self.Usage.get_view(view.id, "search")["arch"]
        for field in ("legacy_name", "ot_number", "folio", "name"):
            self.assertIn(field, arch, "El buscador debe cubrir %s" % field)
