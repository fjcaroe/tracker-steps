"""Validate the branded views and use the native dispatch in the copy only."""
from odoo.tools import config


def layout_check(env, uid, exercise=False):
    assert env.cr.dbname == "ECOPLANTAS" or env.cr.dbname.startswith("ECOPLANTAS_GH_QA_")
    assert not exercise or env.cr.dbname.startswith("ECOPLANTAS_GH_QA_")
    user = env["res.users"].browse(uid)
    action = env.ref("step_ecoplantas_greenhouse.action_greenhouse")
    assert user.active and not user.share and user.action_id == action
    business = env(user=user, su=False, context=dict(env.context, allowed_company_ids=user.company_ids.ids))
    dashboard = business["res.company"].get_steps_greenhouse_dashboard()
    assert dashboard["planned"] == 100 and dashboard["operations"] == 2
    assert all(dashboard[key] for key in ("receipt", "batch", "inspection", "dispatch", "project", "maintenance", "plant"))
    assert business.ref("step_ecoplantas_greenhouse.menu_greenhouse").id in business["ir.ui.menu"]._visible_menu_ids()
    assert not env["ir.mail_server"].search_count([("active", "=", True)])
    for key in ("receipt", "batch", "inspection", "dispatch", "maintenance"):
        entry = dashboard[key]
        view = business[entry["model"]].get_view(view_type="form")
        assert "o_ecoplantas_native_form" in view["arch"], key

    dispatch = business["stock.picking"].browse(dashboard["dispatch"]["id"])
    assert dispatch.state == "draft" and dispatch.move_ids.product_uom_qty == 60
    result = {"native_forms": True, "home_action": True, "draft_dispatch": dispatch.id,
              "planned_dispatch_units": 60}
    if exercise:
        flow = scenario(env, uid, exercise=True)
        assert flow["traceable_input_output"] and flow["quality_passed"]
        batch = business["mrp.production"].browse(dashboard["batch"]["id"])
        lot = batch.lot_producing_id
        assert lot and lot.product_id == dispatch.move_ids.product_id
        dispatch.action_confirm()
        dispatch.action_assign()
        assert dispatch.state == "assigned" and dispatch.move_line_ids.lot_id == lot
        dispatch.move_ids.picked = True
        dispatch.with_context(skip_backorder=True).button_validate()
        available = business["stock.quant"]._get_available_quantity(lot.product_id, dispatch.location_id, lot_id=lot)
        assert dispatch.state == "done" and available == 40
        assert dispatch.move_line_ids.lot_id == lot
        actual_check = business["res.company"].get_steps_greenhouse_dashboard()["inspection"]
        assert actual_check["model"] == "quality.check" and actual_check["status"]
        result.update(flow=flow, dispatched_units=60, remaining_units=40, same_manufactured_lot=True)
    return result
