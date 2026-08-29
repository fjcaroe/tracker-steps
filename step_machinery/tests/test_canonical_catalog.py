# -*- coding: utf-8 -*-
"""Catálogo canónico de conceptos, cuentas y diario de maquinaria."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.step_machinery.models.type_service_machinery import (
    CANONICAL_ABONO_ACCOUNT,
    CANONICAL_CARGO_ACCOUNT,
    CANONICAL_SERVICES,
    TEMP_CODE_PREFIX,
)

CANONICAL_CODES = [code for code, _label in CANONICAL_SERVICES]


@tagged("post_install", "-at_install")
class TestCanonicalCatalog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Service = cls.env["type.service.machinery"]

    def _catalog(self, company=None):
        company = company or self.company
        return self.Service.search([("company_id", "in", (company.id, False))])

    def test_catalog_has_the_eight_canonical_concepts(self):
        self.Service._ensure_canonical_catalog(self.company)
        catalog = self._catalog()
        self.assertEqual(sorted(catalog.mapped("cod")), CANONICAL_CODES)
        for code, label in CANONICAL_SERVICES:
            record = catalog.filtered(lambda r, c=code: r.cod == c)
            self.assertEqual(len(record), 1, "El código %s debe existir una sola vez." % code)
            self.assertTrue(record.name)
        self.assertFalse(
            catalog.filtered(lambda r: (r.cod or "").startswith(TEMP_CODE_PREFIX)),
            "No deben quedar códigos temporales de migración.",
        )

    def test_all_concepts_have_canonical_accounts(self):
        self.Service._ensure_canonical_catalog(self.company)
        catalog = self._catalog()
        for record in catalog:
            self.assertTrue(record.cargo_account_id, "%s sin cuenta de cargo" % record.cod)
            self.assertTrue(record.abono_account_id, "%s sin cuenta de abono" % record.cod)
            self.assertEqual(record.cargo_account_id.code, CANONICAL_CARGO_ACCOUNT[0])
            self.assertEqual(record.abono_account_id.code, CANONICAL_ABONO_ACCOUNT[0])

    def test_catalog_is_idempotent(self):
        first = self.Service._ensure_canonical_catalog(self.company)
        count_first = len(self._catalog())
        second = self.Service._ensure_canonical_catalog(self.company)
        count_second = len(self._catalog())
        self.assertEqual(count_first, count_second, "La segunda pasada no debe duplicar.")
        self.assertEqual(count_second, len(CANONICAL_SERVICES))
        self.assertFalse(second["conceptos_creados"], "Nada que crear en la segunda pasada.")
        self.assertFalse(second["conceptos_normalizados"], "Nada que renumerar en la segunda pasada.")
        self.assertFalse(second["relaciones_asignadas"], "Las cuentas ya estaban asignadas.")
        self.assertTrue(first["empresas"])

    def test_swapped_codes_are_repaired_without_losing_relations(self):
        """Reproduce el estado de Demo: códigos intercambiados y concepto faltante."""
        self.Service._ensure_canonical_catalog(self.company)
        catalog = self._catalog()
        preventiva = catalog.filtered(lambda r: r.cod == "07")
        depreciacion = catalog.filtered(lambda r: r.cod == "08")
        mano_obra = catalog.filtered(lambda r: r.cod == "05")
        # Una relación existente que debe sobrevivir a la normalización.
        vehicle_model = self.env["fleet.vehicle.model"].search([], limit=1)
        if not vehicle_model:
            brand = self.env["fleet.vehicle.model.brand"].create({"name": "Marca catálogo"})
            vehicle_model = self.env["fleet.vehicle.model"].create(
                {"name": "Modelo catálogo", "brand_id": brand.id})
        vehicle = self.env["fleet.vehicle"].create({
            "model_id": vehicle_model.id, "license_plate": "TEST-CAT-01", "es_maquina": True,
        })
        ratio = self.env["monthly.radio.line"].create({
            "name": "Ratio preventiva", "vehicle_id": vehicle.id,
            "service_machinery_id": preventiva.id, "cost_hr_amount": 5.0,
        })
        preventiva_id, depreciacion_id = preventiva.id, depreciacion.id

        # Estado "Demo": preventiva con 05, depreciación con 07, sin Mano de Obra.
        mano_obra.unlink()
        depreciacion.write({"cod": "%sTMP" % TEMP_CODE_PREFIX})
        self.env.flush_all()
        preventiva.write({"cod": "05"})
        self.env.flush_all()
        depreciacion.write({"cod": "07"})
        self.env.flush_all()
        self.assertEqual(len(self._catalog()), 7)
        # El estado roto debe estar realmente en base antes de homologar: así
        # la prueba reproduce el fallo real de Demo (unique(cod, company_id)).
        self.env.invalidate_all()
        self.env.cr.execute(
            "SELECT cod FROM type_service_machinery WHERE id IN %s ORDER BY id",
            (tuple([preventiva_id, depreciacion_id]),))
        self.assertEqual([row[0] for row in self.env.cr.fetchall()], ["05", "07"])

        self.Service._ensure_canonical_catalog(self.company)
        self.env.flush_all()

        catalog = self._catalog()
        self.assertEqual(sorted(catalog.mapped("cod")), CANONICAL_CODES)
        self.assertEqual(self.Service.browse(preventiva_id).cod, "07")
        self.assertEqual(self.Service.browse(depreciacion_id).cod, "08")
        self.assertEqual(ratio.service_machinery_id.id, preventiva_id,
                         "La relación existente debe seguir apuntando al mismo concepto.")
        self.assertTrue(catalog.filtered(lambda r: r.cod == "05").name)

    def test_missing_accounts_are_created_by_orm(self):
        Account = self.env["account.account"].with_company(self.company)
        for code, _name, _atype in (CANONICAL_CARGO_ACCOUNT, CANONICAL_ABONO_ACCOUNT):
            existing = Account.search([("code", "=", code)])
            if existing:
                existing.write({"code": "ZZ%s" % code})
        report = self.Service._ensure_canonical_catalog(self.company)
        self.assertTrue(report["cuentas_creadas"], "Debe crear las cuentas faltantes.")
        cargo = Account.search([("code", "=", CANONICAL_CARGO_ACCOUNT[0])], limit=1)
        abono = Account.search([("code", "=", CANONICAL_ABONO_ACCOUNT[0])], limit=1)
        self.assertEqual(cargo.account_type, CANONICAL_CARGO_ACCOUNT[2])
        self.assertEqual(abono.account_type, CANONICAL_ABONO_ACCOUNT[2])
        self.assertIn(self.company, cargo.company_ids)
        self.assertIn(self.company, abono.company_ids)

    def _new_journal(self, code):
        """Diario limpio: Odoo no deja restringir cuentas si ya hay apuntes."""
        return self.env["account.journal"].create({
            "name": "QA %s" % code, "code": code, "type": "general",
            "company_id": self.company.id,
        })

    def test_journal_accepts_canonical_accounts(self):
        journal = self._new_journal("QAJ1")
        self.company.step_journal_machinery = journal
        # Diario restringido a una cuenta ajena, como estaba CDMaq.
        other = self.env["account.account"].with_company(self.company).search(
            [("account_type", "=", "asset_current")], limit=1)
        if other:
            journal.write({"account_control_ids": [(6, 0, other.ids)]})
        self.Service._ensure_canonical_catalog(self.company)
        allowed = set(journal.account_control_ids.mapped("code"))
        self.assertIn(CANONICAL_CARGO_ACCOUNT[0], allowed)
        self.assertIn(CANONICAL_ABONO_ACCOUNT[0], allowed)
        if other:
            self.assertIn(other.code, allowed, "No se debe quitar una cuenta ya autorizada.")

    def test_unrestricted_journal_is_left_alone(self):
        journal = self._new_journal("QAJ2")
        self.company.step_journal_machinery = journal
        report = self.Service._ensure_canonical_catalog(self.company)
        self.assertFalse(journal.account_control_ids)
        self.assertIn("sin restricción", report["diario"])

    def test_renamed_concept_is_matched_by_code_and_not_duplicated(self):
        """Si la casa renombró un concepto, el código lo sigue identificando."""
        self.Service._ensure_canonical_catalog(self.company)
        renamed = self._catalog().filtered(lambda r: r.cod == "05")
        renamed.write({"name": "Mano de obra propia de la casa"})
        self.env.flush_all()
        report = self.Service._ensure_canonical_catalog(self.company)
        self.env.flush_all()
        catalog = self._catalog()
        self.assertEqual(len(catalog), len(CANONICAL_SERVICES), "No debe duplicar el concepto.")
        self.assertFalse(report["conceptos_creados"])
        self.assertEqual(renamed.name, "Mano de obra propia de la casa",
                         "El nombre elegido por la casa se respeta.")
        self.assertEqual(renamed.cod, "05")
        self.assertFalse(catalog.filtered(lambda r: (r.cod or "").startswith(TEMP_CODE_PREFIX)))
