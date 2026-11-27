"""Measure the original audit fields of support tickets and their three masters, including a rolled-back stage change."""
import hashlib
import json
from pathlib import Path


COPIES = {"MANAGEMENT_QA_STEPS_CRM_20261126U42C", "COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3"}
FIELDS = ("create_date", "write_date", "create_uid", "write_uid")
MODELS = ("helpdesk.ticket", "helpdesk.team", "helpdesk.stage", "helpdesk.tag")


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def inventory(env):
    result = {}
    for name in MODELS:
        model = env[name]
        excluded = sorted(set(FIELDS) - model._fields.keys())
        result[name] = {"automatic_audit": bool(model._log_access), "absent": excluded}
        if not excluded:
            values = model.with_context(active_test=False).search([], order="id").read(["id", *FIELDS], load=None)
            result[name].update(records=len(values), values_sha256=signature(values),
                                column_types=[(model._fields[n].type, model._fields[n].store) for n in FIELDS])
    return result


def run(env, trial=True):
    assert env.cr.dbname in COPIES and __debug__
    assert {r.split(":")[0].strip() for r in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    env.cr.rollback()
    result = inventory(env)
    if not trial:
        env.cr.rollback()
        return result
    user = env["res.users"].browse(7)
    assert user.active and not user.share and not user.has_group("base.group_system")
    scope = env(user=user.id, su=False, context={"allowed_company_ids": [user.company_id.id], "tracking_disable": True,
                                                "mail_create_nosubscribe": True, "mail_notify_force_send": False})
    model = scope["helpdesk.ticket"]
    assert model._log_access and not scope.su
    try:
        existing = model.search([("team_id", "!=", False), ("stage_id", "!=", False), ("partner_id", "!=", False)], order="id", limit=1)
        assert existing
        target = model.search([("team_id", "=", existing.team_id.id), ("stage_id", "!=", False),
                               ("stage_id", "!=", existing.stage_id.id)], order="id", limit=1).stage_id
        assert target
        row = model.create({"name": "Ensayo de campos de auditoría", "team_id": existing.team_id.id, "partner_id": existing.partner_id.id,
                            "stage_id": existing.stage_id.id})
        scope.flush_all()
        values = row.read(list(FIELDS), load=None)[0]
        assert values["create_uid"] == values["write_uid"] == user.id and values["create_date"] and values["write_date"]
        row.write({"stage_id": target.id})
        scope.flush_all()
        row.invalidate_recordset()
        updated = row.read(list(FIELDS), load=None)[0]
        assert row.stage_id == target and updated["create_uid"] == values["create_uid"] and updated["create_date"] == values["create_date"]
        assert updated["write_uid"] == user.id and updated["write_date"] >= values["write_date"]
        return {"historical": result, "ordinary_operator": user.id, "created_by_operator": True,
                "timestamped_create": True, "stage_change_kept_creator": True, "timestamped_write": True}
    finally:
        env.cr.rollback()
