"""Collect a private reference matrix from an isolated original Odoo library (for the Community probe)."""
import json
import os
import re
from pathlib import Path

from odoo.exceptions import AccessError


def capture(env):
    assert re.fullmatch(r"MANAGEMENT_QA_(SYS_LABOR_DOC|CERRO_CUSTODY)_[A-Z0-9_]+", env.cr.dbname)
    assert {row.split(":")[0].strip() for row in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    env.cr.rollback()
    env.cr.execute("SET TRANSACTION READ ONLY")
    env.cr.execute("SELECT id FROM documents_document ORDER BY id")
    result = {"documents": [row[0] for row in env.cr.fetchall()], "users": {}}
    originals = env["res.users"].with_context(active_test=False).search([
        ("active", "=", True), ("id", "!=", 1),
    ]) | env.ref("base.public_user")
    for user in originals:
        assignments = user.company_ids
        scopes = [tuple(assignments.filtered("active").ids), (user.company_id.id,), tuple(assignments.ids),
                  *((company.id,) for company in assignments)]
        info = {"internal": user.has_group("base.group_user"), "cases": {}}
        for company_ids in dict.fromkeys(scopes):
            scope = env(user=user.id, su=False, context={"allowed_company_ids": list(company_ids), "active_test": False})
            key = ",".join(map(str, company_ids))
            try:
                rows = scope["documents.document"].search([], order="id").read(["user_permission"], load=None)
            except AccessError:
                info["cases"][key] = {"view": [], "edit": [], "none": [], "model_acl": False}
                continue
            assert all(row["user_permission"] in ("view", "edit", "none", False) for row in rows)
            case = {role: [row["id"] for row in rows if (row["user_permission"] or "none") == role]
                    for role in ("view", "edit", "none")}
            info["cases"][key] = dict(case, model_acl=True)
        result["users"][str(user.id)] = info
    env.cr.rollback()
    return result


if "env" in globals():
    destination = Path(os.environ["STEPS_LIBRARY_MATRIX"])
    with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        json.dump(capture(env), output, separators=(",", ":"))
