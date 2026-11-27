"""Read the original public employee directory with each SyS operator's company restrictions."""

import hashlib
import json

from odoo.exceptions import AccessError


def employee_directory(shell):
    shell.cr.rollback()
    shell.cr.execute("SET TRANSACTION READ ONLY")
    users = shell["res.users"].sudo().search([("share", "=", False), ("active", "=", True), ("id", ">", 1)], order="id")
    result = {}
    for user in users:
        for company in user.company_ids.filtered("active"):
            scope = shell(user=user.id, su=False, context={"allowed_company_ids": [company.id]})
            assert not scope.su and scope.company == company
            key = str(user.id) + "/" + str(company.id)
            employees = scope["hr.employee.public"]
            try:
                rows = employees.search_read([("company_id", "=", company.id)], ["id", "company_id", "name", "department_id"],
                                             order="id", load=False)
            except AccessError:
                result[key] = {"read": False}
                continue
            assert all(r["company_id"] == company.id for r in rows)
            result[key] = {"read": True, "visible": len(rows), "digest": hashlib.sha256(
                json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    assert len(users) == 2 and result
    shell.cr.rollback()
    return result
