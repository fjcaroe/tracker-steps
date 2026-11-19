import base64
import io

import openpyxl

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from ..models.actual_costs import HEADERS


def actual_cost_sample(env):
    env = env(context=dict(env.context, no_reset_password=True, tracking_disable=True,
        mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False))
    company = env.company
    plans = env["account.analytic.plan"].create([
        {"name": "QA T229 " + name, "default_applicability": "optional"}
        for name in ("Temporada", "Centros", "Actividad")
    ])
    company.write(dict(zip(("management_actual_season_plan_id", "management_actual_center_plan_id",
                            "management_actual_activity_plan_id"), plans.ids)))
    child = env["account.analytic.plan"].create({"name": "QA T229 subcentros", "parent_id": plans[1].id})
    analytics = env["account.analytic.account"].create([
        {"name": "QA T229 " + name, "plan_id": plan.id, "company_id": company.id}
        for name, plan in (("Temporada", plans[0]), ("Centro A", plans[1]), ("Centro B", child), ("Actividad", plans[2]))
    ])
    group = env["step.management.budget.group"].create({"name": "QA T229 grupo", "code": "QA229-%s" % company.id,
        "company_id": company.id, "origin_id": env.ref("step_budget_design.origin_labor").id})
    category = env["product.category"].create({"name": "QA T229 categoría", "management_budget_group_id": group.id})
    subcategory = env["product.category"].create({"name": "QA T229 subcategoría", "parent_id": category.id})
    product = env["product.product"].create({"name": "QA T229 producto", "categ_id": subcategory.id})
    accounts = env["account.account"].create([
        {"name": "QA T229 " + name, "code": code + str(company.id), "account_type": kind,
         "company_ids": [Command.set(company.ids)]}
        for name, code, kind in (("Gasto", "Q229E", "expense"), ("Contrapartida", "Q229A", "asset_current"))
    ])
    journal = env["account.journal"].create({"name": "QA T229 diario", "code": "Q229", "type": "general", "company_id": company.id})
    env["res.currency.rate"].create([
        {"currency_id": env.ref("base." + code).id, "company_id": company.id, "name": "2026-11-01", "rate": rate}
        for code, rate in (("CLP", 1), ("USD", .001))
    ])
    return {"env": env, "company": company, "plans": plans, "analytics": analytics,
        "centers": analytics[1:3], "group": group, "product": product, "accounts": accounts, "journal": journal}


def actual_cost_move(sample, distribution=None, amount=100000, foreign=True, post=True, name="QA T229 gasto"):
    env, analytics = sample["env"], sample["analytics"]
    if distribution is None:
        distribution = {",".join(str(row.id) for row in (analytics[0], center, analytics[3])): pct
                        for center, pct in zip(sample["centers"], (40, 60))}
    currency = env.ref("base.USD" if foreign else "base.CLP")
    move = env["account.move"].with_context(validate_analytic=False).create({
        "move_type": "entry", "journal_id": sample["journal"].id, "date": "2026-11-15",
        "line_ids": [Command.create({"name": name, "account_id": sample["accounts"][0].id,
            "debit": amount, "currency_id": currency.id, "amount_currency": amount / 1000 if foreign else amount,
            "quantity": 10, "product_id": sample["product"].id, "product_uom_id": env.ref("uom.product_uom_unit").id,
            "analytic_distribution": distribution}),
            Command.create({"name": "QA T229 contrapartida", "account_id": sample["accounts"][1].id, "credit": amount})],
    })
    if post:
        move.action_post()
    return move


def actual_cost_rows(sample, move, user=None):
    model = sample["env"]["step.management.actual.cost.report"]
    if user:
        model = model.with_user(user)
    return model.search([("move_id", "=", move.id)], order="center_id,id")


def exercise_booked_operational_currency(sample, user):
    env = sample["env"]
    usd = env.ref("base.USD")
    move = actual_cost_move(sample, foreign=False, post=False)
    move.write({"operational_currency_id": usd.id})
    move.observed_exchange_rate = 1250
    move.action_post()
    source = move.line_ids.filtered("analytic_distribution")
    assert source.operational_debit == 80 and source.debit == 100000
    # The existing ledger remains usable when historical rates are corrected
    # or removed. Only the fixture's own company rates are touched.
    env["res.currency.rate"].search([
        ("company_id", "=", sample["company"].id), ("currency_id", "=", usd.id)]).unlink()
    before = (source.debit, source.credit, source.amount_currency, source.operational_debit,
              source.operational_credit, source.operational_exchange_rate)
    rows = actual_cost_rows(sample, move, user)
    assert rows.mapped("debit_usd") == [32, 48] and all(rows.mapped("usd_available"))
    assert sum(rows.mapped("debit_clp")) == 100000
    assert before == (source.debit, source.credit, source.amount_currency, source.operational_debit,
                      source.operational_credit, source.operational_exchange_rate)
    return rows


@tagged("post_install", "-at_install")
class ActualCostCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env["res.company"].create({"name": "QA T229 empresa", "currency_id": cls.env.ref("base.CLP").id})
        cls.env = cls.env["res.company"].with_company(company).with_context(
            allowed_company_ids=company.ids, no_reset_password=True).env
        cls.sample = actual_cost_sample(cls.env)
        cls.reader = new_test_user(cls.env, login="qa-t229-reader", company_id=company.id,
            company_ids=[Command.set(company.ids)],
            groups="step_management_costs.group_management_readonly,account.group_account_readonly")

    def test_posted_native_allocations_and_all_dimensions(self):
        move = actual_cost_move(self.sample, post=False)
        self.assertFalse(actual_cost_rows(self.sample, move, self.reader))
        move.action_post()
        rows = actual_cost_rows(self.sample, move, self.reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.center_id, self.sample["centers"])
        self.assertEqual(rows.mapped("quantity"), [4, 6])
        self.assertEqual(rows.mapped("debit_clp"), [40000, 60000])
        self.assertEqual(rows.mapped("debit_usd"), [40, 60])
        self.assertEqual(rows.season_ids, self.sample["analytics"][0])
        self.assertEqual(rows.activity_ids, self.sample["analytics"][3])
        self.assertEqual(rows.group_id, self.sample["group"])
        self.assertEqual(rows.origin_id, self.env.ref("step_budget_design.origin_labor"))
        self.assertEqual(sum(rows.mapped("debit_clp")), sum(move.line_ids.mapped("debit")))
        self.assertTrue(all(rows.mapped("distribution_valid")))

    def test_independent_plans_partial_allocation_and_unassigned_amount(self):
        analytics = self.sample["analytics"]
        move = actual_cost_move(self.sample, {str(analytics[0].id): 100, str(analytics[3].id): 100, str(analytics[1].id): 40})
        rows = actual_cost_rows(self.sample, move, self.reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(rows.mapped("debit_clp")), 100000)
        self.assertEqual(sum(rows.mapped("debit_usd")), 100)
        self.assertEqual(rows.filtered("center_id").debit_clp, 40000)
        self.assertEqual(rows.filtered(lambda row: not row.center_id).debit_clp, 60000)
        self.assertEqual(rows.season_ids, analytics[0])
        self.assertEqual(rows.activity_ids, analytics[3])
        no_center = actual_cost_move(self.sample, {str(analytics[0].id): 100, str(analytics[3].id): 100})
        self.assertEqual(len(actual_cost_rows(self.sample, no_center, self.reader)), 1)

    def test_filters_preserve_the_matching_allocation(self):
        sample = self.sample
        other_season = self.env["account.analytic.account"].create({"name": "QA T229 otra temporada", "plan_id": sample["plans"][0].id, "company_id": self.env.company.id})
        distribution = {",".join(map(str, (season.id, center.id, sample["analytics"][3].id))): pct
            for season, center, pct in ((sample["analytics"][0], sample["centers"][0], 40), (other_season, sample["centers"][1], 60))}
        move = actual_cost_move(sample, distribution)
        model = self.env["step.management.actual.cost.report"].with_user(self.reader)
        domain = [("move_id", "=", move.id)]
        rows = model.search(domain + [("season_ids", "in", sample["analytics"][0].ids)])
        self.assertEqual(rows.center_id, sample["centers"][0])
        self.assertEqual(rows.debit_clp, 40000)
        self.assertEqual(len(model.search(domain + [("group_id", "=", sample["group"].id)])), 2)
        self.assertEqual(len(model.search(domain + [("origin_id", "=", sample["group"].origin_id.id)])), 2)
        self.assertFalse(model.search(domain + [("season_ids", "=", False)]))
        self.assertEqual(len(model.search(domain + [("season_ids", "not in", other_season.ids)])), 1)

    def test_reversal_keeps_the_accounting_debit_and_credit(self):
        move = actual_cost_move(self.sample)
        reversal = move.with_context(validate_analytic=False)._reverse_moves(default_values_list=[{"date": "2026-11-16"}], cancel=False)
        reversal.action_post()
        rows = actual_cost_rows(self.sample, reversal, self.reader)
        self.assertEqual(sum(rows.mapped("credit_clp")), 100000)
        self.assertEqual(sum(rows.mapped("credit_usd")), 100)
        self.assertEqual(sum(rows.mapped("debit_clp")), 0)

    def test_rounding_residue_and_stable_selection_ids(self):
        sample = self.sample
        third = self.env["account.analytic.account"].create({"name": "QA T229 Centro C", "plan_id": sample["plans"][1].id, "company_id": self.env.company.id})
        centers = sample["centers"] | third
        # Odoo stores analytical percentages at two decimal places. Test a
        # complete split, then verify currency rounding in stable numeric order.
        distribution = {str(center.id): pct for center, pct in zip(centers, (33.33, 33.33, 33.34))}
        pending = actual_cost_move(sample, distribution, amount=100, post=False)
        move = actual_cost_move(sample, distribution, amount=100)
        rows = actual_cost_rows(sample, move, self.reader).sorted("id")
        ids = rows.ids
        self.assertEqual(rows.mapped("debit_clp"), [33, 33, 34])
        self.assertEqual(rows.mapped("debit_usd"), [.03, .03, .04])
        self.assertAlmostEqual(sum(rows.mapped("quantity")), 10)
        pending.action_post()
        self.assertEqual(actual_cost_rows(sample, move, self.reader).sorted("id").ids, ids)

    def test_missing_real_rate_leaves_excel_cells_and_totals_empty(self):
        self.env["res.currency.rate"].search([("company_id", "in", [False, self.env.company.id]), ("currency_id", "=", self.env.ref("base.USD").id)]).unlink()
        move = actual_cost_move(self.sample, foreign=False)
        rows = actual_cost_rows(self.sample, move, self.reader)
        self.assertTrue(all(rows.mapped("clp_available")))
        self.assertFalse(any(rows.mapped("usd_available")))
        book = openpyxl.load_workbook(io.BytesIO(rows._excel_bytes()), data_only=True)
        self.assertIsNone(book.active["M3"].value)
        self.assertIsNone(book.active["M5"].value)
        self.assertIn("sin tasa contable", book.active["A7"].value)

    def test_operational_usd_uses_the_booked_ledger_not_a_later_rate(self):
        if "operational_debit" not in self.env["account.move.line"]._fields:
            self.skipTest("The optional Steps operational ledger is not installed")
        exercise_booked_operational_currency(self.sample, self.reader)

    def test_excel_contract_and_native_source_are_preserved(self):
        move = actual_cost_move(self.sample, name='=HYPERLINK("https://example.invalid","test")')
        before = [(line.id, line.debit, line.credit, line.amount_currency, line.analytic_distribution) for line in move.line_ids]
        rows = actual_cost_rows(self.sample, move, self.reader)
        result = rows.action_export_excel()
        self.assertEqual(result["target"], "download")
        download = self.env["step.management.actual.cost.export"].with_user(self.reader).search([], order="id desc", limit=1)
        book = openpyxl.load_workbook(io.BytesIO(base64.b64decode(download.file)), data_only=True)
        sheet = book.active
        self.assertEqual(tuple(cell.value for cell in sheet[2]), HEADERS)
        self.assertEqual(sheet["F3"].value, 4)
        self.assertEqual(sheet["K5"].value, 100000)
        self.assertEqual(sheet["M5"].value, 100)
        self.assertEqual(sheet["E3"].data_type, "s")
        self.assertEqual(sheet.freeze_panes, "C3")
        self.assertEqual(sheet.auto_filter.ref, "A2:Q4")
        self.assertEqual(before, [(line.id, line.debit, line.credit, line.amount_currency, line.analytic_distribution) for line in move.line_ids])

    def test_company_and_native_journal_item_rules_cannot_be_bypassed(self):
        visible = actual_cost_move(self.sample)
        hidden = actual_cost_move(self.sample, name="QA T229 HIDDEN")
        hidden_rows = actual_cost_rows(self.sample, hidden)
        self.env["ir.rule"].create({"name": "QA T229 source visibility", "model_id": self.env.ref("account.model_account_move_line").id,
            "domain_force": "[('name', '!=', 'QA T229 HIDDEN')]"})
        self.assertEqual(len(actual_cost_rows(self.sample, visible, self.reader)), 2)
        self.assertFalse(actual_cost_rows(self.sample, hidden, self.reader))
        with self.assertRaises(AccessError):
            hidden_rows.with_user(self.reader).read(["debit_clp"])
        with self.assertRaises(AccessError):
            hidden_rows.with_user(self.reader).action_export_excel()
        other = self.env["res.company"].create({"name": "QA T229 otra empresa", "currency_id": self.env.ref("base.CLP").id})
        native = self.sample["env"]["res.company"].with_company(other).env
        sample = actual_cost_sample(native)
        foreign = actual_cost_move(sample)
        foreign_rows = actual_cost_rows(sample, foreign)
        with self.assertRaises(AccessError):
            foreign_rows.with_user(self.reader).with_context(allowed_company_ids=self.env.company.ids).read(["debit_clp"])

    def test_planning_access_alone_does_not_grant_accounting_access(self):
        move = actual_cost_move(self.sample)
        planner = new_test_user(self.env, login="qa-t229-no-ledger", company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)], groups="step_management_costs.group_management_user")
        with self.assertRaises(AccessError):
            actual_cost_rows(self.sample, move, planner)
        with self.assertRaises(AccessError):
            actual_cost_rows(self.sample, move).with_user(planner).action_export_excel()

    def test_report_is_read_only_and_opens_the_existing_entry(self):
        move = actual_cost_move(self.sample)
        rows = actual_cost_rows(self.sample, move, self.reader)
        action = rows[0].action_open_move()
        self.assertEqual((action["res_model"], action["res_id"]), ("account.move", move.id))
        with self.assertRaises(AccessError):
            rows.write({"name": "Changed"})
        with self.assertRaises(AccessError):
            rows.unlink()
        self.assertTrue(move.exists())

    def test_inconsistent_distribution_is_visible_and_cannot_be_exported(self):
        move = actual_cost_move(self.sample, {str(self.sample["centers"][0].id): 200})
        rows = actual_cost_rows(self.sample, move, self.reader)
        self.assertFalse(rows.distribution_valid)
        self.assertFalse(rows.clp_available)
        self.assertTrue(rows.fx_note)
        with self.assertRaises(UserError):
            rows.action_export_excel()
