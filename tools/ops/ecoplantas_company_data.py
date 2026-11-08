"""Portable native records for the audited, draft-only EcoPlantas demo."""
from collections import Counter
import json

from odoo import Command
from odoo.exceptions import AccessError, UserError

GREENHOUSE = "steps_ecoplantas_greenhouse"
COST = "step_nursery_shared_costs"
# Order follows native record dependencies. Generated MRP moves and work
# orders are checked after creation rather than copied as independent rows.
FIELDS = {
    "res.partner": "name is_company type street street2 city zip phone mobile email website country_id state_id",
    "product.template": "name type tracking is_storable default_code uom_id uom_po_id categ_id sale_ok purchase_ok list_price standard_price description",
    "product.product": "product_tmpl_id",
    "stock.location": "name usage location_id barcode active",
    "mrp.workcenter": "name code time_efficiency costs_hour default_capacity time_start time_stop active",
    "mrp.bom": "product_tmpl_id product_id product_qty product_uom_id type code consumption active",
    "mrp.routing.workcenter": "name bom_id workcenter_id sequence time_mode time_cycle_manual",
    "mrp.bom.line": "bom_id product_id product_qty product_uom_id operation_id sequence",
    "stock.picking": "origin partner_id picking_type_id location_id location_dest_id scheduled_date priority note",
    "stock.move": "name picking_id product_id product_uom_qty product_uom location_id location_dest_id sequence date date_deadline",
    "mrp.production": "origin product_id product_qty product_uom_id bom_id picking_type_id location_src_id location_dest_id date_start date_deadline priority user_id",
    "quality.alert.team": "name sequence",
    "quality.point": "title note test_type_id team_id product_ids picking_type_ids measure_on measure_frequency_type",
    "project.project": "name description privacy_visibility active",
    "project.task.type": "name sequence fold project_ids",
    "project.task": "name description project_id stage_id priority state date_deadline user_ids active",
    "maintenance.team": "name",
    "maintenance.equipment": "name workcenter_id maintenance_team_id model serial_no note active",
    "maintenance.request": "name equipment_id maintenance_team_id maintenance_type request_date schedule_date duration description stage_id",
    "step.sawmill.costing.driver": "name uom_id sequence active",
    "account.analytic.account": "name code plan_id step_cost_pool step_cost_parent_id active",
    "step.nursery.cost.rule": "parent_id labor_id driver_id",
    "step.nursery.cost.measure": "center_id driver_id week_start quantity",
    "account.analytic.line": "name date amount unit_amount product_id step_cost_labor_id account_id",
    "step.nursery.cost.run": "parent_id week_start",
}
COMPANY_ONLY = {
    "res.partner", "product.template", "stock.location", "mrp.workcenter", "mrp.bom", "stock.picking", "stock.move",
    "mrp.production", "quality.alert.team", "quality.point", "project.project", "project.task", "maintenance.equipment",
    "maintenance.request", "maintenance.team", "step.sawmill.costing.driver", "account.analytic.account", "step.nursery.cost.measure",
    "account.analytic.line",
}
QUIET = {"tracking_disable": True, "mail_notrack": True, "mail_create_nosubscribe": True,
         "mail_notify_force_send": False, "mail_auto_subscribe_no_notify": True}


def key(record):
    return f"{record._name}:{record.id}"


def export_demo(env, uid):
    assert env.cr.dbname == "ECOPLANTAS"
    company = env.ref("base.main_company")
    assert company.name == "ECOPLANTAS" and company.chart_template == "cl"
    env = env(context=dict(env.context, allowed_company_ids=company.ids, active_test=False, lang=None))
    warehouse, = env["stock.warehouse"].search([("company_id", "=", company.id)])
    refs = env["ir.model.data"].search([
        "|", ("module", "=", GREENHOUSE), "&", ("module", "=", COST), ("name", "=like", "demo_%"),
    ], order="module,name")
    records = {model: env[model] for model in FIELDS}
    bindings = {}
    for ref in refs:
        record = env[ref.model].browse(ref.res_id).exists()
        assert record and ref.model in records
        records[ref.model] |= record
        bindings[f"{ref.module}.{ref.name}"] = key(record)
    batch, = records["mrp.production"]
    bom, = records["mrp.bom"]
    run, = records["step.nursery.cost.run"]
    inspection, = records["quality.point"]
    dispatch = env.ref(f"{GREENHOUSE}.dispatch")
    records["res.partner"] = dispatch.partner_id
    records["product.template"] |= records["product.product"].product_tmpl_id
    records["product.product"] |= records["product.template"].product_variant_ids
    records["mrp.routing.workcenter"] = bom.operation_ids
    records["mrp.bom.line"] = bom.bom_line_ids
    records["stock.move"] = records["stock.picking"].move_ids
    records["quality.alert.team"] = inspection.team_id
    records["maintenance.team"] = records["maintenance.equipment"].maintenance_team_id | records["maintenance.request"].maintenance_team_id
    records["step.nursery.cost.rule"] = run.parent_id.step_cost_rule_ids

    assert batch.state == run.state == "draft" and not run.item_ids
    assert all(picking.state == "draft" for picking in records["stock.picking"])
    for model in ("account.move", "purchase.order", "sale.order", "crm.lead", "stock.move.line",
                  "stock.quant", "stock.lot", "quality.check"):
        assert not env[model].search_count([("company_id", "=", company.id)]), f"New {model} in source"
    for model in COMPANY_ONLY - {"res.partner", "stock.location", "stock.move", "quality.alert.team", "maintenance.team"}:
        assert set(env[model].search([("company_id", "=", company.id)]).ids) == set(records[model].ids), (
            f"Unexpected company records in {model}"
        )
    partners = env["res.partner"].search([("company_id", "=", company.id)])
    assert not (partners - records["res.partner"] - env["res.users"].search([]).partner_id)
    assert set(env["stock.move"].search([("company_id", "=", company.id)]).ids) == set(
        (records["stock.move"] | batch.move_raw_ids | batch.move_finished_ids).ids
    )
    assert len(batch.workorder_ids) == len(bom.operation_ids)
    assert all(not order.qty_produced for order in batch.workorder_ids)
    assert len(records["product.product"]) == len(records["product.template"])

    special = {
        key(company): "company", key(warehouse.lot_stock_id): "stock",
        key(warehouse.in_type_id): "incoming", key(warehouse.out_type_id): "outgoing",
        key(warehouse.manu_type_id): "manufacture", key(env["res.users"].browse(uid)): "reviewer",
    }
    graph = {key(record) for group in records.values() for record in group}

    def encode(record):
        if not record:
            return False
        name = key(record)
        if name in graph:
            return {"record": name}
        if name in special:
            return {"special": special[name]}
        external_id = record.get_external_id().get(record.id)
        assert external_id, f"Unmapped dependency: {record._name}"
        return {"xmlid": external_id, "model": record._name}

    rows, attachments = [], []
    for model, fields in FIELDS.items():
        group = records[model]
        if model == "account.analytic.account":
            group = group.sorted(lambda item: not item.step_cost_pool)
        else:
            group = group.sorted("id")
        for record in group:
            values = {}
            for field in fields.split():
                if field not in record._fields:
                    continue
                item = record[field]
                kind = record._fields[field].type
                if kind == "many2one":
                    item = encode(item)
                elif kind == "many2many":
                    item = [encode(child) for child in item]
                values[field] = item
            rows.append({"key": key(record), "model": model, "values": values})
            assert not env["mail.message"].search_count([
                ("model", "=", model), ("res_id", "=", record.id), ("message_type", "in", ["comment", "email"]),
            ]), f"Manual chatter needs an explicit mapping for {model}"
            for attachment in env["ir.attachment"].search([("res_model", "=", model), ("res_id", "=", record.id),
                                                           ("res_field", "=", False)]):
                assert attachment.type == "binary" and not attachment.public
                attachments.append({"record": key(record), "name": attachment.name,
                                    "mimetype": attachment.mimetype, "datas": attachment.datas.decode()})
    return {
        "company": company.name, "currency": company.currency_id.name,
        "rows": rows, "xmlids": bindings, "attachments": attachments,
        "workorders": len(batch.workorder_ids), "production_moves": len(batch.move_raw_ids | batch.move_finished_ids),
        "cost_total": run.cost_total, "cost_week": str(run.week_start),
        "cost_split": sorted((line.labor_id.name, line.center_id.name, line.amount) for line in run.line_ids),
    }


def target_context(env, cid, uid):
    assert env.cr.dbname == "LAB_TAREAS" or env.cr.dbname.startswith("ECOPLANTAS_DEV_QA_")
    company = env["res.company"].browse(cid).exists()
    user = env["res.users"].browse(uid).exists()
    assert company.name.casefold() == "ecoplantas" and company.active and not company.parent_id
    assert company.chart_template == "cl" and user.active and not user.share and company in user.company_ids
    assert user.has_group("base.group_system") and user.has_group("account.group_account_manager")
    env = env(context=dict(env.context, **QUIET, allowed_company_ids=company.ids))
    warehouse, = env["stock.warehouse"].search([("company_id", "=", cid)])
    return env, company.with_env(env), user.with_env(env), warehouse


def import_demo(env, payload, cid, uid):
    env, company, user, warehouse = target_context(env, cid, uid)
    assert company.currency_id.name == payload["currency"]
    assert not any(env.ref(xid, raise_if_not_found=False) for xid in payload["xmlids"]), "Already imported or conflicting XML IDs"
    common = {"company": company, "stock": warehouse.lot_stock_id, "incoming": warehouse.in_type_id,
              "outgoing": warehouse.out_type_id, "manufacture": warehouse.manu_type_id, "reviewer": user}
    assert all(common.values())
    created = {}

    def decode(pointer):
        if "record" in pointer:
            return created[pointer["record"]].id
        if "special" in pointer:
            return common[pointer["special"]].id
        record = env.ref(pointer["xmlid"])
        assert record._name == pointer["model"]
        if record._name == "res.users":
            assert company in record.company_ids, "Assignee lacks access to EcoPlantas"
        elif "company_id" in record._fields:
            assert not record.company_id or record.company_id == company, f"Cross-company dependency: {record._name}"
        return record.id

    for item in payload["rows"]:
        model = item["model"]
        values = {}
        for field, value in item["values"].items():
            assert field in env[model]._fields, f"Missing native field {model}.{field}"
            if isinstance(value, dict):
                value = decode(value)
            elif isinstance(value, list):
                value = [Command.set([decode(entry) for entry in value])]
            values[field] = value
        if model in COMPANY_ONLY:
            values["company_id"] = company.id
        if model == "product.product":
            record, = env["product.template"].browse(values["product_tmpl_id"]).product_variant_ids
        else:
            record = env[model].with_company(company).create(values)
        created[item["key"]] = record
    for xid, name in payload["xmlids"].items():
        module, local = xid.split(".", 1)
        record = created[name]
        env["ir.model.data"].create({"module": module, "name": local, "model": record._name,
                                     "res_id": record.id, "noupdate": True})
    for item in payload["attachments"]:
        record = created[item["record"]]
        env["ir.attachment"].create({"name": item["name"], "datas": item["datas"], "mimetype": item["mimetype"],
                                     "res_model": record._name, "res_id": record.id, "company_id": company.id})
    groups = ("step_ecoplantas_greenhouse.group_greenhouse", "maintenance.group_equipment_manager", "mrp.group_mrp_routings")
    user.write({"groups_id": [Command.link(env.ref(group).id) for group in groups]})
    business = env(user=user, su=False)
    run = business.ref(f"{COST}.demo_run")
    run.action_preview()
    proof = verify_demo(env, payload, cid, uid)
    proof["records"] = dict(Counter(item["model"] for item in payload["rows"]))
    proof["attachments"] = len(payload["attachments"])
    return proof


def verify_demo(env, payload, cid, uid):
    env, company, user, warehouse = target_context(env, cid, uid)
    business = env(user=user, su=False)
    demo = lambda name: business.ref(f"{GREENHOUSE}.{name}")
    receipt, batch, dispatch = (demo(name) for name in ("receipt", "batch", "dispatch"))
    run = business.ref(f"{COST}.demo_run")
    assert all(record.company_id == company for record in (receipt, batch, dispatch, run))
    assert receipt.state == batch.state == dispatch.state == run.state == "draft"
    assert receipt.picking_type_id == warehouse.in_type_id and dispatch.picking_type_id == warehouse.out_type_id
    assert batch.picking_type_id == warehouse.manu_type_id
    assert len(batch.workorder_ids) == payload["workorders"]
    assert len(batch.move_raw_ids | batch.move_finished_ids) == payload["production_moves"]
    assert str(run.week_start) == payload["cost_week"] and run.cost_total == payload["cost_total"]
    split = sorted([line.labor_id.name, line.center_id.name, line.amount] for line in run.line_ids)
    assert split == payload["cost_split"], "Cost preview differs"
    assert not run.item_ids
    dashboard = business["res.company"].get_steps_greenhouse_dashboard()
    assert dashboard["batch"]["id"] == batch.id and dashboard["shared_costs"]
    assert business.ref("step_ecoplantas_greenhouse.menu_greenhouse").id in business["ir.ui.menu"]._visible_menu_ids()
    for record in (receipt, batch, dispatch, demo("inspection"), demo("pump_check"), run):
        assert record.get_view(view_type="form")["arch"]
    try:
        business["res.company"].with_company(user.company_id).get_steps_greenhouse_dashboard()
    except (AccessError, UserError):
        pass
    else:
        assert user.company_id == company, "Dashboard opened in another company"
    return {"company": cid, "reviewer": uid, "warehouse": warehouse.id, "drafts": True,
            "planned": dashboard["planned"], "operations": dashboard["operations"], "tasks": dashboard["tasks"],
            "cost_total": run.cost_total, "cost_lines": len(run.line_ids), "forms_and_company_scope": True}


def exercise_demo(env, payload, cid, uid):
    assert env.cr.dbname.startswith("ECOPLANTAS_DEV_QA_")
    env, company, user, _warehouse = target_context(env, cid, uid)
    business = env(user=user, su=False)
    demo = lambda name: business.ref(f"{GREENHOUSE}.{name}")
    receipt, batch, dispatch = (demo(name) for name in ("receipt", "batch", "dispatch"))
    seed, plant = demo("seed"), demo("plant")
    seed_lot = business["stock.lot"].create({"name": "SEMILLA-TRASLADO-QA", "product_id": seed.id, "company_id": cid})
    receipt.action_confirm()
    for move in receipt.move_ids:
        move.quantity = move.product_uom_qty
        if move.product_id == seed:
            move.move_line_ids.lot_id = seed_lot
        move.picked = True
    receipt.with_context(skip_backorder=True).button_validate()
    assert receipt.state == "done"
    batch.action_confirm()
    batch.action_assign()
    checks = business["quality.check"].search([("production_id", "=", batch.id), ("point_id", "=", demo("inspection").id)])
    assert checks and all(check.quality_state == "none" for check in checks)
    checks.do_pass()
    lot = business["stock.lot"].create({"name": "PLANTINES-TRASLADO-QA", "product_id": plant.id, "company_id": cid})
    batch.lot_producing_id = lot
    batch.qty_producing = batch.product_qty
    batch._set_qty_producing()
    for workorder in batch.workorder_ids:
        workorder.button_finish()
    batch.with_context(skip_backorder=True).button_mark_done()
    assert batch.state == "done" and seed_lot in batch.move_raw_ids.move_line_ids.lot_id
    dispatch.action_confirm()
    dispatch.action_assign()
    assert dispatch.state == "assigned" and dispatch.move_line_ids.lot_id == lot
    dispatch.move_ids.picked = True
    dispatch.with_context(skip_backorder=True).button_validate()
    remaining = business["stock.quant"]._get_available_quantity(plant, dispatch.location_id, lot_id=lot)
    assert dispatch.state == "done" and remaining == batch.product_qty - dispatch.move_ids.quantity
    run = business.ref(f"{COST}.demo_run")
    run.action_confirm()
    assert run.state == "done" and sum(run.item_ids.mapped("amount")) == 0
    run.action_reverse()
    assert run.state == "reversed"
    return {"received": True, "produced": batch.product_qty, "quality": True,
            "shipped": dispatch.move_ids.quantity, "same_lot": True, "remaining": remaining,
            "cost_total": run.cost_total, "cost_confirmed_and_reversed": True}
