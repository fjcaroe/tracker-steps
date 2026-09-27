# -*- coding: utf-8 -*-
"""Costeo con los ocho conceptos y contabilización sobre el catálogo canónico."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.step_machinery.models.type_service_machinery import (
    CANONICAL_ABONO_ACCOUNT,
    CANONICAL_CARGO_ACCOUNT,
    CANONICAL_SERVICES,
)

#: Costo por hora asignado a cada concepto distinto del combustible.
HOURLY_RATES = {"02": 10.0, "03": 8.0, "04": 6.0, "05": 20.0, "06": 15.0, "07": 5.0, "08": 2.0}
FUEL_UNIT_PRICE = 100.0
HOURS = 2.0
LITRES = 3.0


@tagged("post_install", "-at_install")
class TestMachineryAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Service = cls.env["type.service.machinery"]
        # Diario propio de la prueba, restringido igual que CDMaq antes de la
        # homologación: sólo acepta una cuenta ajena a maquinaria.
        cls.journal = cls.env["account.journal"].create({
            "name": "QA Costeo Maquinarias", "code": "QAMAQ", "type": "general",
            "company_id": cls.company.id,
        })
        cls.company.step_journal_machinery = cls.journal
        cls.foreign_account = cls.env["account.account"].with_company(cls.company).search(
            [("account_type", "=", "asset_current")], limit=1)
        if cls.foreign_account:
            cls.journal.write({"account_control_ids": [(6, 0, cls.foreign_account.ids)]})
        cls.Service._ensure_canonical_catalog(cls.company)
        cls.cargo = cls.env["account.account"].with_company(cls.company).search(
            [("code", "=", CANONICAL_CARGO_ACCOUNT[0])], limit=1)
        cls.abono = cls.env["account.account"].with_company(cls.company).search(
            [("code", "=", CANONICAL_ABONO_ACCOUNT[0])], limit=1)

        cls.product = cls.env["product.template"].create(
            {"name": "Combustible contable", "standard_price": FUEL_UNIT_PRICE})
        vehicle_model = cls.env["fleet.vehicle.model"].search([], limit=1)
        if not vehicle_model:
            brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Marca contable"})
            vehicle_model = cls.env["fleet.vehicle.model"].create(
                {"name": "Modelo contable", "brand_id": brand.id})
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "model_id": vehicle_model.id, "license_plate": "TEST-MQ-CONTA",
            "es_maquina": True, "step_product_id": cls.product.id, "step_total_hrs_mes": 100,
        })
        services = {s.cod: s for s in cls.Service.search(
            [("company_id", "in", (cls.company.id, False))])}
        for code, rate in HOURLY_RATES.items():
            cls.env["monthly.radio.line"].create({
                "name": "Tarifa %s" % code, "vehicle_id": cls.vehicle.id,
                "service_machinery_id": services[code].id, "cost_hr_amount": rate,
            })

    def _usage(self, company=None):
        company = company or self.company
        usage = self.env["step.hrs.machinery"].create({
            "date": "2026-08-28", "folio": "QA-CONTA",
            "company_id": company.id, "state": "done",
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": self.vehicle.id,
            "hrs_maquina": HOURS, "lrts_combustible": LITRES,
        })
        return usage

    def test_catalog_covers_the_eight_cost_components(self):
        usage = self._usage()
        usage.action_cost()
        line = usage.hrs_machinery_line
        components = line._cost_components()
        self.assertEqual(sorted(components), [code for code, _l in CANONICAL_SERVICES])
        self.assertEqual(components["01"], FUEL_UNIT_PRICE * LITRES)
        for code, rate in HOURLY_RATES.items():
            self.assertAlmostEqual(components[code], rate * HOURS, places=2,
                                   msg="Concepto %s mal costeado" % code)
        expected_total = FUEL_UNIT_PRICE * LITRES + sum(HOURLY_RATES.values()) * HOURS
        self.assertAlmostEqual(line.total_machine_cost, expected_total, places=2)
        self.assertAlmostEqual(line.total_hour_cost, expected_total / HOURS, places=2)

    def test_move_is_balanced_and_uses_canonical_accounts(self):
        usage = self._usage()
        usage.action_cost()
        usage.action_conta()
        move = usage.invoice_id
        self.assertEqual(usage.state, "accounted")
        self.assertTrue(move)
        debit = sum(move.line_ids.mapped("debit"))
        credit = sum(move.line_ids.mapped("credit"))
        self.assertAlmostEqual(debit, credit, places=2)
        expected_total = FUEL_UNIT_PRICE * LITRES + sum(HOURLY_RATES.values()) * HOURS
        self.assertAlmostEqual(debit, expected_total, places=2)
        debit_accounts = move.line_ids.filtered(lambda l: l.debit).mapped("account_id")
        credit_accounts = move.line_ids.filtered(lambda l: l.credit).mapped("account_id")
        self.assertEqual(debit_accounts, self.cargo)
        self.assertEqual(credit_accounts, self.abono)
        self.assertEqual(move.ref, usage.name)

    def test_journal_accepts_both_canonical_accounts(self):
        allowed = self.journal.account_control_ids
        self.assertTrue(allowed, "El escenario parte con el diario restringido.")
        self.assertIn(self.cargo, allowed)
        self.assertIn(self.abono, allowed)

    def _plan(self, name):
        plan = self.env["account.analytic.plan"].search([("name", "=", name)], limit=1)
        return plan or self.env["account.analytic.plan"].create({"name": name})

    def _analytic(self, name, plan_name):
        return self.env["account.analytic.account"].create(
            {"name": name, "plan_id": self._plan(plan_name).id})

    def _usage_with_three_plans(self):
        """Escenario de la corrección: Temporada, Centro de costos y Actividad."""
        self.season_account = self._analytic("T26-27 QA", "Temporada QA")
        self.center_account = self._analytic("Centro QA maquinaria", "Centro de costos QA")
        self.activity_account = self._analytic("Aplicaciones QA", "Actividad QA")
        season = self.env["step.temporada"].create({
            "name": "T26-27 QA", "start_date": "2026-08-01", "end_date": "2027-07-31",
            "company_id": self.company.id, "cost_id": self.season_account.id,
        })
        activity = self.env["step.actividad"].create({
            "name": "Aplicaciones QA", "company_id": self.company.id,
            "cost_id": self.activity_account.id,
        })
        if activity.id == self.activity_account.id:
            # El escenario debe poder distinguir el maestro de su cuenta.
            self.activity_account = self._analytic("Aplicaciones QA 2", "Actividad QA")
            activity.cost_id = self.activity_account
        uom = self.env.ref("uom.product_uom_hour", raise_if_not_found=False)             or self.env["uom.uom"].search([], limit=1)
        labor = self.env["step.labor"].create({
            "name": "Aplicar pulverización QA", "actividad_id": activity.id,
            "uom_id": uom.id, "uom_trato": uom.id,
            "grupo_labor": "manten", "met_costeo": "udm",
        })
        usage = self._usage()
        # La temporada del encabezado se resuelve por fecha. Si la base ya trae
        # otra que cubre el rango, se usa esa y se le da la misma cuenta.
        self.assertTrue(usage.temp_id, "El registro debe quedar con temporada.")
        if usage.temp_id != season:
            usage.temp_id.cost_id = self.season_account
        usage.hrs_machinery_line.write(
            {"cost_id": self.center_account.id, "labor_id": labor.id})
        return usage

    def test_debit_distribution_uses_the_three_analytic_plans(self):
        usage = self._usage_with_three_plans()
        usage.action_cost()
        usage.action_conta()
        debit_lines = usage.invoice_id.line_ids.filtered(lambda l: l.debit)
        self.assertTrue(debit_lines)
        expected_ids = {self.season_account.id, self.center_account.id,
                        self.activity_account.id}
        for line in debit_lines:
            self.assertTrue(line.analytic_distribution,
                            "El cargo debe llevar distribución analítica.")
            found = set()
            for key, percentage in line.analytic_distribution.items():
                self.assertEqual(percentage, 100.0)
                found.update(int(item) for item in key.split(","))
            self.assertEqual(found, expected_ids)

    def test_activity_uses_its_analytic_account_not_its_own_id(self):
        """La regresión corregida: se repartía por el id de `step.actividad`."""
        usage = self._usage_with_three_plans()
        activity = usage.hrs_machinery_line.actividad_id
        self.assertNotEqual(activity.id, self.activity_account.id,
                            "El escenario debe distinguir maestro y cuenta analítica.")
        usage.action_cost()
        usage.action_conta()
        debit = usage.invoice_id.line_ids.filtered(lambda l: l.debit)[0]
        keys = set()
        for key in debit.analytic_distribution:
            keys.update(int(item) for item in key.split(","))
        self.assertIn(self.activity_account.id, keys)
        self.assertNotIn(activity.id, keys)

    def test_repeated_plan_does_not_break_posting(self):
        """Registros antiguos con el centro de costos en el plan Temporada."""
        usage = self._usage_with_three_plans()
        intruder = self._analytic("Centro mal clasificado", "Temporada QA")
        usage.hrs_machinery_line.cost_id = intruder
        usage.action_cost()
        usage.action_conta()
        debit = usage.invoice_id.line_ids.filtered(lambda l: l.debit)[0]
        keys = set()
        for key in debit.analytic_distribution:
            keys.update(int(item) for item in key.split(","))
        # Gana la temporada del encabezado; la cuenta repetida se descarta.
        self.assertIn(self.season_account.id, keys)
        self.assertNotIn(intruder.id, keys)
        self.assertIn(self.activity_account.id, keys)

    def test_liability_line_carries_no_analytic_distribution(self):
        """La cuenta de pasivo no lleva analítica: sólo las cuentas de gasto."""
        usage = self._usage_with_three_plans()
        usage.action_cost()
        usage.action_conta()
        credit_lines = usage.invoice_id.line_ids.filtered(lambda l: l.credit)
        self.assertTrue(credit_lines)
        for line in credit_lines:
            self.assertFalse(line.analytic_distribution,
                             "El abono al pasivo no debe llevar cuenta analítica.")

    def test_cannot_post_twice(self):
        usage = self._usage()
        usage.action_cost()
        usage.action_conta()
        with self.assertRaises(UserError):
            usage.action_conta()
        self.assertEqual(
            self.env["account.move"].search_count([("ref", "=", usage.name)]), 1)

    def test_multi_company_uses_its_own_accounts_and_journal(self):
        other = self.env["res.company"].create({"name": "Maquinaria Contable SpA"})
        report = self.Service._ensure_canonical_catalog(other)
        self.assertTrue(report["empresas"])
        catalog = self.Service.search([("company_id", "=", other.id)])
        self.assertEqual(sorted(catalog.mapped("cod")), [c for c, _l in CANONICAL_SERVICES])
        cargo = self.env["account.account"].with_company(other).search(
            [("code", "=", CANONICAL_CARGO_ACCOUNT[0])], limit=1)
        abono = self.env["account.account"].with_company(other).search(
            [("code", "=", CANONICAL_ABONO_ACCOUNT[0])], limit=1)
        self.assertTrue(cargo and abono)
        self.assertIn(other, cargo.company_ids)
        self.assertIn(other, abono.company_ids)
        for record in catalog:
            # `code` es dependiente de la empresa: hay que leerlo en su contexto.
            self.assertEqual(record.cargo_account_id, cargo)
            self.assertEqual(record.abono_account_id, abono)
            self.assertEqual(
                record.cargo_account_id.with_company(other).code, CANONICAL_CARGO_ACCOUNT[0])
            self.assertEqual(
                record.abono_account_id.with_company(other).code, CANONICAL_ABONO_ACCOUNT[0])
        self.assertNotEqual(cargo, self.cargo,
                            "Cada empresa usa su propia cuenta canónica.")
