"""Run with Odoo shell. All test writes are rolled back, including on failure."""
import json

try:
    checks = [("account.analytic.account", "has_cost"), ("step.cuartel.line", "has_cuartel")]
    if "step.management.cost.center" in env and "agri_hectares" in env["step.management.cost.center"]._fields:
        checks.append(("step.management.cost.center", "agri_hectares"))
    for model, field in checks:
        definition = env[model].fields_get([field])[field]
        assert definition["type"] == "float", (model, definition)
        assert tuple(definition["digits"]) == (16, 2), (model, definition)
        metadata = env["ir.model.fields"].search([("model", "=", model), ("name", "=", field)])
        assert metadata.ttype == "float", (model, metadata.ttype)
    account = env["account.analytic.account"].search([], limit=1)
    if not account:
        plan = env["account.analytic.plan"].create({"name": "T49 rollback plan"})
        fundo = env["step.fundo"].create({"name": "T49 rollback fundo"})
        account = env["account.analytic.account"].create({
            "name": "T49 rollback account", "plan_id": plan.id, "fundo_id": fundo.id,
            "type_costo": "fruta", "etapa_costo": "ope", "tipo_fruta": "conven",
        })
    account.with_context(tracking_disable=True).write({"has_cost": 1.14})
    account.flush_recordset(["has_cost"])
    account.invalidate_recordset(["has_cost"])
    assert abs(account.has_cost - 1.14) < 1e-9, account.has_cost
    cuartel = env["step.cuartel.line"].create({"name": "T49 rollback cuartel", "centro_id": account.id, "has_cuartel": 0.27})
    cuartel.flush_recordset(["has_cuartel"])
    cuartel.invalidate_recordset(["has_cuartel"])
    assert abs(cuartel.has_cuartel - 0.27) < 1e-9, cuartel.has_cuartel
    for value in (0.0, 3.0, 12.99):
        cuartel.has_cuartel = value
        cuartel.flush_recordset(["has_cuartel"])
        cuartel.invalidate_recordset(["has_cuartel"])
        assert abs(cuartel.has_cuartel - value) < 1e-9
    if len(checks) == 3:
        center = env["step.management.cost.center"].search([("analytic_account_id", "=", account.id)], limit=1)
        if not center:
            center = env["step.management.cost.center"].create({
                "code": "T49-ROLLBACK", "name": "T49 rollback center",
                "analytic_account_id": account.id, "company_id": account.company_id.id or env.company.id,
            })
        assert abs(center.agri_hectares - 1.14) < 1e-9, center.agri_hectares
    print("T49_VERIFY_OK " + json.dumps({"database": env.cr.dbname, "fields": checks, "values": [1.14, 0.27, 0, 3, 12.99]}))
finally:
    env.cr.rollback()
