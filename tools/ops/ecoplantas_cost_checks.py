"""Native ECOPLANTAS cost walkthrough under the review user's actual roles."""
from odoo import Command
from odoo.exceptions import AccessError, UserError


def verify_costs(env, uid, *, prepare=False, exercise=False):
    assert env.cr.dbname == "ECOPLANTAS" or env.cr.dbname.startswith("ECOPLANTAS_GH_QA_")
    assert not exercise or env.cr.dbname.startswith("ECOPLANTAS_GH_QA_")
    user = env["res.users"].browse(uid)
    company = env.ref("base.main_company")
    business = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids))
    assert user.active and not user.share and user.has_group("account.group_account_manager")
    ref = lambda key: business.ref("step_nursery_shared_costs.demo_" + key)
    run = ref("run")
    parent, north, south = (ref(key) for key in ("parent", "north", "south"))
    column = parent.plan_id._column_name()
    lines = business["account.analytic.line"]
    assert north.step_cost_parent_id == parent and south.step_cost_parent_id == parent
    assert business["res.company"].get_steps_greenhouse_dashboard()["shared_costs"]
    assert business.ref("step_nursery_shared_costs.menu_cost_run").id in business["ir.ui.menu"]._visible_menu_ids()
    assert "step_cost_pool" in parent.get_view(view_type="form")["arch"]
    assert "action_confirm" in run.get_view(view_type="form")["arch"]
    assert "step_cost_labor_id" in business["account.move"].get_view(view_type="form")["arch"]
    assert run.state == "draft" and not run.item_ids
    if prepare:
        run.action_preview()
    assert run.cost_total == 200000 and len(run.line_ids) == 4
    assert {child.id: sum(run.line_ids.filtered(lambda line: line.center_id == child).mapped("amount"))
            for child in (north, south)} == {north.id: 110000, south.id: 90000}
    assert set(run.line_ids.driver_id.ids) == set(parent.step_cost_rule_ids.driver_id.ids)
    proof = {"draft": run.id, "total": 200000, "north": 110000, "south": 90000,
             "rules": 2, "measures": 4, "native_forms": True}
    if not exercise:
        return proof

    def expect_error(callback, exception=UserError):
        try:
            with business.cr.savepoint():
                callback()
        except exception:
            return
        raise AssertionError("The operation should have been rejected")

    def balance(account):
        return sum(lines.search([(column, "=", account.id), ("company_id", "=", company.id)]).mapped("amount"))

    measures = business["step.nursery.cost.measure"].search([("center_id", "=", north.id)])
    measure = measures.filtered(lambda item: item.driver_id == ref("riego_driver"))
    previous = measure.quantity
    measure.quantity = previous + 1
    expect_error(run.action_confirm)
    measure.quantity = previous
    expect_error(lambda: run.write({"state": "done"}), AccessError)
    assert not run.item_ids
    gl_count = business["account.move"].search_count([])
    run.action_confirm()
    assert run.state == "done" and len(run.item_ids) == 6
    assert (balance(parent), balance(north), balance(south)) == (0, -110000, -90000)
    assert business["account.move"].search_count([]) == gl_count
    expect_error(run.action_confirm)
    duplicate = business["step.nursery.cost.run"].create({"parent_id": parent.id, "week_start": run.week_start})
    expect_error(duplicate.action_preview)
    expect_error(lambda: ref("riego_charge").write({"amount": -1}))
    run.action_reverse()
    assert run.state == "reversed" and len(run.item_ids.filtered("step_cost_is_reversal")) == 6
    assert (balance(parent), balance(north), balance(south)) == (-200000, 0, 0)

    # A regular posted journal entry allocates a real expense to the same
    # analytic center and a second native plan. The cost transfer keeps both.
    other_plan = business["account.analytic.plan"].create({"name": "Dimensión de prueba"})
    other = business["account.analytic.account"].create({
        "name": "Segundo eje QA", "plan_id": other_plan.id, "company_id": company.id,
    })
    accounts = business["account.account"]
    expense = accounts.search([("company_ids", "in", company.id), ("account_type", "=", "expense")], limit=1)
    asset = accounts.search([("company_ids", "in", company.id), ("account_type", "=", "asset_current")], limit=1)
    journal = business["account.journal"].search([("company_id", "=", company.id), ("type", "=", "general")], limit=1)
    entry = business["account.move"].create({
        "move_type": "entry", "date": run.week_start, "journal_id": journal.id,
        "line_ids": [
            Command.create({"name": "Costo QA", "account_id": expense.id, "debit": 1001,
                            "step_cost_labor_id": ref("riego").id, "analytic_distribution": {f"{parent.id},{other.id}": 100}}),
            Command.create({"name": "Contrapartida QA", "account_id": asset.id, "credit": 1001}),
        ],
    })
    entry.action_post()
    source = entry.line_ids.filtered(lambda line: line.account_id == expense).analytic_line_ids
    assert source and source.step_cost_labor_id == ref("riego")
    duplicate.action_preview()
    duplicate.action_confirm()
    transfers = duplicate.item_ids.filtered(lambda item: item.step_cost_source_id == source)
    assert len(transfers) == 3 and sum(transfers.mapped("amount")) == 0
    assert all(item[other_plan._column_name()] == other for item in transfers)
    assert entry.state == "posted" and source.amount == -1001
    proof.update(stale_preview_blocked=True, duplicate_blocked=True, reversed=True,
                 posted_source_preserved=True, second_analytic_dimension=True)
    return proof
