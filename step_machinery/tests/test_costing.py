from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMachineryCosting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.product = cls.env["product.template"].create({"name": "Combustible prueba", "standard_price": 100})
        vehicle_model = cls.env["fleet.vehicle.model"].search([], limit=1)
        if not vehicle_model:
            brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Prueba Maquinaria"})
            vehicle_model = cls.env["fleet.vehicle.model"].create({
                "name": "Tractor de prueba", "brand_id": brand.id,
            })
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "model_id": vehicle_model.id,
            "license_plate": "TEST-MQ-COST",
            "es_maquina": True,
            "step_product_id": cls.product.id,
            "step_total_hrs_mes": 100,
        })
        # Los ocho conceptos de costo deben existir para poder contabilizar.
        cls.services = {}
        for code in ("01", "02", "03", "04", "05", "06", "07", "08"):
            service = cls.env["type.service.machinery"].search([("cod", "=", code)], limit=1)
            if not service:
                service = cls.env["type.service.machinery"].create({"name": "Prueba %s" % code, "cod": code})
            cls.services[code] = service
        for code, rate, target in (("02", 10.0, "consumption"), ("07", 5.0, "radio"), ("08", 2.0, "radio")):
            service = cls.services[code]
            model = "monthly.consumption.line" if target == "consumption" else "monthly.radio.line"
            cls.env[model].create({
                "name": "Prueba %s" % code, "vehicle_id": cls.vehicle.id,
                "service_machinery_id": service.id, "cost_hr_amount": rate,
            })

    def _usage(self):
        usage = self.env["step.hrs.machinery"].create({
            "date": "2026-08-15", "folio": "TEST-MQ", "company_id": self.company.id, "state": "done",
        })
        line = self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": self.vehicle.id,
            "hrs_maquina": 2.0, "lrts_combustible": 3.0,
        })
        return usage, line

    def test_cost_snapshot_by_concept(self):
        usage, line = self._usage()
        usage.action_cost()
        self.assertEqual(usage.state, "costed")
        self.assertEqual(line.fuel_total_cost, 300.0)
        self.assertEqual(line.oil_total_cost, 20.0)
        self.assertEqual(line.preventive_total_cost, 10.0)
        self.assertEqual(line.depreciation_total_cost, 4.0)
        self.assertEqual(line.total_machine_cost, 334.0)
        self.assertEqual(line.total_hour_cost, 167.0)

    def test_calendar_week_is_derived_from_date(self):
        usage, _line = self._usage()
        self.assertEqual(usage.week_number, 33)

    def test_account_move_is_balanced(self):
        usage, _line = self._usage()
        usage.action_cost()
        journal = self.env["account.journal"].search([
            ("company_id", "=", self.company.id), ("type", "=", "general")
        ], limit=1)
        account = self.env["account.account"].search([], limit=1)
        self.assertTrue(journal and account)
        self.company.step_journal_machinery = journal
        for service in self.env["type.service.machinery"].search([]):
            service.cargo_account_id = account
            service.abono_account_id = account
        usage.action_conta()
        self.assertEqual(usage.state, "accounted")
        self.assertTrue(usage.invoice_id)
        self.assertAlmostEqual(
            sum(usage.invoice_id.line_ids.mapped("debit")),
            sum(usage.invoice_id.line_ids.mapped("credit")), places=2,
        )
