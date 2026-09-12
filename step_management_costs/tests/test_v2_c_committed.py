"""Corte V2 C — comprometido de compras y cantidad neta por comprar
(`PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`).

Audita el modelo real `purchase.order(.line)` (instalado en `LAB_TAREAS`,
`account_budget` también instalado pero descartado — J5: "no se ajusta a lo
que se diseñó en este módulo"). El comprometido se lee de OC confirmadas y
no facturadas por completo, nunca de `account_budget`.
"""

from odoo import fields
from odoo.tests import tagged

from .test_management_costs import ManagementCostsCommon, extra_product_vals


@tagged("post_install", "-at_install")
class TestV2CCommitted(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor V2C"})
        cls.prod = cls.env["product.product"].create(dict({
            "name": "Insumo comprometido", "type": "consu", "is_storable": True,
            "uom_id": cls.env.ref("uom.product_uom_unit").id,
            "uom_po_id": cls.env.ref("uom.product_uom_unit").id,
        }, **extra_product_vals(cls.env)))

    def _po_line(self, product_qty=10.0, state="purchase", company=None):
        company = company or self.company_a
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "company_id": company.id,
            "order_line": [(0, 0, {
                "product_id": self.prod.id, "product_qty": product_qty,
                "product_uom": self.prod.uom_po_id.id, "price_unit": 10.0,
                "name": self.prod.name,
            })],
        })
        if state == "purchase":
            po.button_confirm()
        elif state == "cancel":
            po.button_cancel()
        return po.order_line

    def _invoice_line(self, po_line, quantity, post=True):
        move = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": po_line.order_id.partner_id.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "product_id": po_line.product_id.id, "quantity": quantity,
                "price_unit": po_line.price_unit, "purchase_line_id": po_line.id,
                "name": po_line.product_id.name,
            })],
        })
        if post:
            move.action_post()
        return move

    def _requirement(self, **kw):
        vals = {
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": "season", "include_budgets": False, "include_programs": False,
        }
        vals.update(kw)
        req = self.env["step.management.stock.requirement"].create(vals)
        return req

    # ------------------------------------------------------------------
    # Estados de OC
    # ------------------------------------------------------------------
    def test_draft_po_excluded(self):
        self._po_line(state="draft")
        req = self._requirement()
        committed, _lines = req._committed_quantity(self.prod)
        self.assertEqual(committed, 0.0)

    def test_confirmed_po_included(self):
        self._po_line(product_qty=10.0)
        req = self._requirement()
        committed, lines = req._committed_quantity(self.prod)
        self.assertAlmostEqual(committed, 10.0)
        self.assertEqual(len(lines), 1)

    def test_cancelled_po_excluded(self):
        line = self._po_line(product_qty=10.0)
        line.order_id.button_cancel()
        req = self._requirement()
        committed, _lines = req._committed_quantity(self.prod)
        self.assertEqual(committed, 0.0)

    def test_partially_invoiced_only_remainder_committed(self):
        line = self._po_line(product_qty=10.0)
        self._invoice_line(line, 4.0)
        req = self._requirement()
        committed, _lines = req._committed_quantity(self.prod)
        self.assertAlmostEqual(committed, 6.0)

    def test_fully_invoiced_excluded(self):
        line = self._po_line(product_qty=10.0)
        self._invoice_line(line, 10.0)
        req = self._requirement()
        committed, _lines = req._committed_quantity(self.prod)
        self.assertAlmostEqual(committed, 0.0)

    def test_draft_invoice_line_already_reduces_qty_invoiced(self):
        # Verificado contra Odoo real: `purchase.order.line.qty_invoiced`
        # (campo núcleo, no propio de este addon) cuenta la línea de factura
        # desde que se crea, sin exigir que la factura esté validada. El
        # comprometido de este addon simplemente lee ese campo tal cual —
        # no reinterpreta ni corrige el criterio de Compras.
        line = self._po_line(product_qty=10.0)
        self._invoice_line(line, 4.0, post=False)
        req = self._requirement()
        committed, _lines = req._committed_quantity(self.prod)
        self.assertAlmostEqual(committed, 6.0)

    # ------------------------------------------------------------------
    # UdM, empresa, trazabilidad
    # ------------------------------------------------------------------
    def test_uom_converted_before_summing(self):
        uom_dozen = self.env.ref("uom.product_uom_dozen")
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id, "company_id": self.company_a.id,
            "order_line": [(0, 0, {
                "product_id": self.prod.id, "product_qty": 2.0,
                "product_uom": uom_dozen.id, "price_unit": 10.0,
                "name": self.prod.name,
            })],
        })
        po.button_confirm()
        req = self._requirement()
        committed, _lines = req._committed_quantity(self.prod)
        self.assertAlmostEqual(committed, 24.0)  # 2 docenas = 24 unidades

    def test_two_companies_not_mixed(self):
        self._po_line(product_qty=10.0, company=self.company_a)
        self._po_line(product_qty=5.0, company=self.company_b)
        req_a = self._requirement(company_id=self.company_a.id)
        committed_a, _l = req_a._committed_quantity(self.prod)
        self.assertAlmostEqual(committed_a, 10.0)

    def test_committed_lines_traceable(self):
        line = self._po_line(product_qty=10.0)
        req = self._requirement()
        _committed, lines = req._committed_quantity(self.prod)
        self.assertEqual(lines, line)

    # ------------------------------------------------------------------
    # `net_to_buy`: no doble descuento con `forecasted`; consumo único
    # ------------------------------------------------------------------
    def _tmpl_and_budget(self, jun=60.0, jul=60.0):
        tmpl = self.env["step.management.budget.template"].create({
            "name": "Plantilla V2C", "company_id": self.company_a.id,
            "base_hectares": self.center_a.hectares, "state": "active",
            "line_ids": [(0, 0, {
                "category": "input", "group_id": self.group_a.id,
                "indicator": "Fert", "product_id": self.prod.id,
                "uom_id": self.prod.uom_id.id, "unit_price": 10.0,
                "jun": jun, "jul": jul,
            })],
        })
        budget = self._new_budget(template=tmpl, centers=[self.center_a])
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        return budget

    def test_net_to_buy_subtracts_committed_once_across_periods(self):
        budget = self._tmpl_and_budget(jun=60.0, jul=60.0)
        self._po_line(product_qty=50.0)  # comprometido = 50
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        self.env["stock.quant"].sudo()._update_available_quantity(
            self.prod, warehouse.lot_stock_id, 60.0,
        )  # stock cubre exactamente junio; julio queda descubierto
        req = self._requirement(
            granularity="month", include_budgets=True,
            budget_ids=[(6, 0, [budget.id])],
        )
        req.action_compute()
        lines = req.line_ids.sorted(key=lambda l: l.period_index)
        self.assertEqual(len(lines), 2)
        # ambas semanas muestran el mismo comprometido informativo
        self.assertAlmostEqual(lines[0].committed_quantity, 50.0, places=2)
        self.assertAlmostEqual(lines[1].committed_quantity, 50.0, places=2)
        # shortage_quantity (R3) no cambia por lo comprometido
        self.assertAlmostEqual(lines[0].shortage_quantity, 0.0, places=2)
        self.assertAlmostEqual(lines[1].shortage_quantity, 60.0, places=2)
        # net_to_buy consume lo comprometido una sola vez: 60 - 50 = 10
        self.assertAlmostEqual(lines[0].net_to_buy, 0.0, places=2)
        self.assertAlmostEqual(lines[1].net_to_buy, 10.0, places=2)

    def test_forecasted_metric_does_not_double_discount_committed(self):
        budget = self._tmpl_and_budget(jun=60.0, jul=0.0)
        self._po_line(product_qty=50.0)
        req = self._requirement(
            granularity="month", include_budgets=True,
            budget_ids=[(6, 0, [budget.id])], availability_metric="forecasted",
        )
        req.action_compute()
        self.assertEqual(len(req.line_ids), 1)  # jul=0 no genera línea
        line = req.line_ids
        # con métrica "forecasted", net_to_buy == shortage_quantity siempre
        # (virtual_available ya incluye lo comprometido; no se descuenta de nuevo)
        self.assertAlmostEqual(line.net_to_buy, line.shortage_quantity, places=2)
        self.assertAlmostEqual(line.committed_quantity, 50.0, places=2)  # informativo igual

    def test_permissions_no_broad_purchase_access_required(self):
        budget = self._tmpl_and_budget(jun=10.0, jul=0.0)
        self._po_line(product_qty=5.0)
        req = self._requirement(
            granularity="season", include_budgets=True,
            budget_ids=[(6, 0, [budget.id])],
        )
        req.with_user(self.user_operator).action_compute()
        line = req.line_ids
        self.assertAlmostEqual(line.committed_quantity, 5.0, places=2)
