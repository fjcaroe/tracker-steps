from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFreightStudioCosting(TransactionCase):
    """Puntos 3 y 4 del documento T27 (migración del formulario Studio a código):
    Tarifas por tramo/modalidad de frío/servicio de flete, y el costeo +
    contabilización del Registro de fletes (botones Calcular costeo /
    Contabilizar en step.freight.order).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # El usuario de pruebas debe poder contabilizar (action_post_freight
        # exige account.group_account_user, igual que el botón en la vista).
        accounting_group = cls.env.ref("account.group_account_user")
        cls.env.user.groups_id = [(4, accounting_group.id)]

        cls.expense_account = cls.env["account.account"].search([
            ("company_ids", "in", cls.company.id),
            ("account_type", "in", ("expense", "expense_direct_cost")),
            ("deprecated", "=", False),
        ], limit=1)
        cls.other_expense_account = cls.env["account.account"].search([
            ("company_ids", "in", cls.company.id),
            ("account_type", "in", ("expense", "expense_direct_cost")),
            ("deprecated", "=", False),
            ("id", "!=", cls.expense_account.id),
        ], limit=1)
        cls.provision_account = cls.env["account.account"].search([
            ("company_ids", "in", cls.company.id),
            ("account_type", "=", "liability_current"),
            ("deprecated", "=", False),
        ], limit=1)
        if not cls.expense_account or not cls.provision_account:
            raise AssertionError(
                "La base de pruebas debe tener un plan contable con cuentas "
                "de gasto y de pasivo corriente."
            )

        cls.journal = cls.env["account.journal"].create({
            "name": "QA Provisión Fletes",
            "code": "QAFLT",
            "type": "general",
            "company_id": cls.company.id,
            "default_account_id": cls.provision_account.id,
        })
        cls.company.freight_provision_journal_id = cls.journal.id

        cls.route = cls.env["step.freight.route"].create({
            "name": "QA Ruta Norte",
            "origin": "Planta",
            "destination": "Puerto",
        })
        cls.other_route = cls.env["step.freight.route"].create({
            "name": "QA Ruta Sur",
            "origin": "Planta",
            "destination": "Frontera",
        })
        cls.cold_mode = cls.env["step.freight.cold.mode"].create({
            "name": "QA Refrigerado",
            "min_temperature": -2,
            "max_temperature": 4,
        })
        cls.carrier = cls.env["res.partner"].create({
            "name": "Transportista QA",
            "supplier_rank": 1,
        })
        cls.freight_product = cls.env["product.template"].create({
            "name": "Flete QA fruta",
            "is_flete": True,
            "property_account_expense_id": cls.expense_account.id,
        })
        cls.other_freight_product = cls.env["product.template"].create({
            "name": "Flete QA frío",
            "is_flete": True,
            "property_account_expense_id": cls.other_expense_account.id
            if cls.other_expense_account
            else cls.expense_account.id,
        })

        cls.tariff = cls.env["step.freight.tariff"].create({
            "name": "Tarifa QA",
            "freight_carrier_id": cls.carrier.id,
            "effective_from": "2026-01-01",
            "tariff_line_ids": [
                (0, 0, {
                    "route_id": cls.route.id,
                    "service_product_id": cls.freight_product.id,
                    "tariff_basis": "Por UdM",
                    "freight_rate": 1000.0,
                }),
                (0, 0, {
                    "route_id": cls.route.id,
                    "cold_mode_id": cls.cold_mode.id,
                    "service_product_id": cls.freight_product.id,
                    "tariff_basis": "Por UdM",
                    "freight_rate": 1500.0,
                }),
                (0, 0, {
                    "route_id": cls.other_route.id,
                    "service_product_id": cls.other_freight_product.id,
                    "tariff_basis": "Por viaje",
                    "freight_rate": 90000.0,
                }),
            ],
        })

    def _order(self, **values):
        vals = {
            "name": "Orden QA",
            "date": "2026-10-01",
            "price_list_id": self.tariff.id,
        }
        vals.update(values)
        return self.env["step.freight.order"].create(vals)

    # --- Tarifas (punto 3): tramo, modalidad de frío y servicio de flete ---

    def test_tariff_line_exposes_route_cold_mode_and_service(self):
        line = self.tariff.tariff_line_ids[0]
        self.assertEqual(line.route_id, self.route)
        self.assertEqual(line.service_product_id, self.freight_product)
        self.assertEqual(line.km_from, self.route.km_from)

    # --- Costeo (punto 4): action_cost_freight ---

    def test_cost_freight_computes_value_as_quantity_times_rate(self):
        order = self._order(detail_ids=[(0, 0, {
            "route_id": self.route.id,
            "service_product_id": self.freight_product.id,
            "quantity": 3,
        })])
        order.action_cost_freight()
        detail = order.detail_ids
        self.assertEqual(detail.unit_rate, 1000.0)
        self.assertEqual(detail.freight_value, 3000.0)
        costs = order.cost_ids
        self.assertEqual(len(costs), 1)
        self.assertEqual(costs.service_product_id, self.freight_product)
        self.assertEqual(costs.freight_cost, 3000.0)
        self.assertEqual(costs.expense_account_id, self.expense_account)

    def test_cost_freight_picks_tariff_line_by_cold_mode(self):
        order = self._order(cold_mode_id=self.cold_mode.id, detail_ids=[(0, 0, {
            "route_id": self.route.id,
            "service_product_id": self.freight_product.id,
            "quantity": 2,
        })])
        order.action_cost_freight()
        detail = order.detail_ids
        # Debe tomar la línea de tarifa en frío (1500), no la estándar (1000).
        self.assertEqual(detail.unit_rate, 1500.0)
        self.assertEqual(detail.freight_value, 3000.0)

    def test_cost_freight_per_trip_mode_ignores_quantity(self):
        order = self._order(detail_ids=[(0, 0, {
            "route_id": self.other_route.id,
            "service_product_id": self.other_freight_product.id,
            "quantity": 7,
        })])
        order.action_cost_freight()
        detail = order.detail_ids
        self.assertEqual(detail.unit_rate, 90000.0)
        # Modalidad "Por viaje": el valor no se multiplica por la cantidad.
        self.assertEqual(detail.freight_value, 90000.0)

    def test_cost_freight_groups_lines_by_product(self):
        order = self._order(detail_ids=[
            (0, 0, {
                "route_id": self.route.id,
                "service_product_id": self.freight_product.id,
                "quantity": 1,
            }),
            (0, 0, {
                "route_id": self.route.id,
                "service_product_id": self.freight_product.id,
                "quantity": 2,
            }),
        ])
        order.action_cost_freight()
        costs = order.cost_ids
        self.assertEqual(len(costs), 1, "Las líneas del mismo producto deben agruparse en un solo costeo.")
        self.assertEqual(costs.freight_cost, 1000.0 + 2000.0)

    def test_cost_report_keeps_each_detail_route(self):
        order = self._order(detail_ids=[
            (0, 0, {
                "route_id": self.route.id,
                "service_product_id": self.freight_product.id,
                "quantity": 2,
            }),
            (0, 0, {
                "route_id": self.other_route.id,
                "service_product_id": self.other_freight_product.id,
                "quantity": 3,
            }),
        ])
        order.action_cost_freight()
        self.env.flush_all()
        rows = self.env["step.freight.cost.report"].search([("order_id", "=", order.id)])
        self.assertEqual(len(rows), 2)
        self.assertEqual({(row.route_id.id, row.amount) for row in rows},
                         {(self.route.id, 2000.0), (self.other_route.id, 90000.0)})

    def test_cost_freight_requires_route_on_detail(self):
        order = self._order(detail_ids=[(0, 0, {
            "service_product_id": self.freight_product.id,
            "quantity": 1,
        })])
        with self.assertRaises(UserError):
            order.action_cost_freight()

    def test_cost_freight_requires_detail_lines(self):
        order = self._order()
        with self.assertRaises(UserError):
            order.action_cost_freight()

    # --- Contabilización (punto 4): action_post_freight ---

    def _costed_order(self, quantity=3):
        order = self._order(detail_ids=[(0, 0, {
            "route_id": self.route.id,
            "service_product_id": self.freight_product.id,
            "quantity": quantity,
        })])
        order.action_cost_freight()
        return order

    def test_post_freight_creates_balanced_move_with_carrier_as_partner(self):
        order = self._costed_order()
        order.action_post_freight()
        move = order.freight_move_id
        self.assertTrue(move)
        self.assertEqual(move.state, "posted")
        debit_lines = move.line_ids.filtered(lambda l: l.debit)
        credit_lines = move.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(debit_lines.mapped("account_id"), self.expense_account)
        self.assertEqual(credit_lines.mapped("account_id"), self.provision_account)
        self.assertEqual(sum(debit_lines.mapped("debit")), 3000.0)
        self.assertEqual(sum(credit_lines.mapped("credit")), 3000.0)
        self.assertTrue(all(line.partner_id == self.carrier for line in move.line_ids))
        self.assertEqual(
            order.freight_state, "status3",
            "La orden debe quedar marcada como Contabilizado.",
        )
        accounting = self.env["step.freight.accounting"].search([("order_id", "=", order.id)])
        self.assertEqual(len(accounting), 1)
        self.assertEqual(accounting.move_id, move)

    def test_post_freight_twice_is_blocked(self):
        order = self._costed_order()
        order.action_post_freight()
        with self.assertRaises(UserError):
            order.action_post_freight()
        self.assertEqual(self.env["account.move"].search_count([("ref", "=", order.name)]), 1)

    def test_post_freight_requires_costing_first(self):
        order = self._order(detail_ids=[(0, 0, {
            "route_id": self.route.id,
            "service_product_id": self.freight_product.id,
            "quantity": 1,
        })])
        with self.assertRaises(UserError):
            order.action_post_freight()

    def test_post_freight_without_journal_configured_raises(self):
        order = self._costed_order()
        self.company.freight_provision_journal_id = False
        with self.assertRaises(UserError):
            order.action_post_freight()

    def test_post_freight_with_account_not_allowed_by_journal_raises(self):
        order = self._costed_order()
        # Restringir el diario a una cuenta que no es la de gasto del producto
        # (igual que "cuenta de cargo no permitida en el diario").
        self.journal.account_control_ids = [(6, 0, self.provision_account.ids)]
        with self.assertRaises(UserError):
            order.action_post_freight()

    def test_post_freight_without_carrier_raises(self):
        order = self._costed_order()
        order.freight_carrier_id = False
        self.tariff.freight_carrier_id = False
        with self.assertRaises(UserError):
            order.action_post_freight()

    def test_post_freight_requires_accounting_group(self):
        order = self._costed_order()
        # No basta con quitar el grupo directo: el usuario admin de pruebas
        # suele tener Contabilidad por un grupo que lo implica (p. ej.
        # Administrador de Facturación). Se usa un usuario nuevo, sin ningún
        # grupo de Contabilidad, para probar el bloqueo de forma confiable.
        plain_user = self.env["res.users"].create({
            "name": "QA sin contabilidad",
            "login": "qa_sin_contabilidad@example.com",
            "email": "qa_sin_contabilidad@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(UserError):
            order.with_user(plain_user).action_post_freight()


@tagged("post_install", "-at_install")
class TestFreightQaFilters(TransactionCase):
    """T27 QA 2026-10-04: transportista, camión y chofer filtrados."""

    def test_domains(self):
        env = self.env
        carrier = env["res.partner"].create({"name": "QA Transportista", "is_freight_carrier": True})
        plain = env["res.partner"].create({"name": "QA Contacto"})
        order_field = env["step.freight.order"]._fields["freight_carrier_id"]
        found = env["res.partner"].search(eval(order_field.domain))
        self.assertIn(carrier, found)
        self.assertNotIn(plain, found)
        detail = env["step.freight.order.line"]._fields
        self.assertIn("step_chofer", detail["driver_id"].domain)
        self.assertIn("carga", detail["vehicle_id"].domain)
