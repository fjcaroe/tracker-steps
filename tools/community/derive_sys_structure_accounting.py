"""Compose the native SyS rule ownership and journal relations on a verified free engine."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory

from build_numeric_input_engine import hashes, require, seal, sha
from original_history_engine_contract import _snapshot


STRUCTURE = "models/hr_payroll_structure.py"
ACCOUNT = "models/hr_payslip.py"
STRUCTURE_SHA = "d51f3a322256947ca0191c5256639ba457232e8312d169900e4a73a9750b979a"
ACCOUNT_SHA = "0df0804e6f29610e1223011526c0caf8e05418b03aaad2475dd674900718a49d"
OWNERSHIP = b'''from odoo import fields, models


class SalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    struct_id = fields.Many2one("hr.payroll.structure", required=True, ondelete="restrict")


class PayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    # OCA inherits rule fields on lines. SyS has no independent structure
    # column there. The rule FK is authoritative even for newly created lines.
    struct_id = fields.Many2one(related="salary_rule_id.struct_id", store=False, readonly=True)
'''
JOURNAL = b'''from odoo import fields, models


class Structure(models.Model):
    _inherit = "hr.payroll.structure"

    journal_id = fields.Many2one("account.journal", string="Salary Journal",
                                 company_dependent=True, copy=False, ondelete="set null")
'''


def plan(modules):
    result = {module: dict(files) for module, files in modules.items()}
    payroll = result["payroll"]
    account = result["payroll_account"]
    for files in (payroll, account):
        require(ast.literal_eval(files["__manifest__.py"].decode()).get("license") == "LGPL-3",
                "SyS accounting requires free engine modules")
    source = payroll[STRUCTURE]
    require(sha(source) == STRUCTURE_SHA, "SyS rule structure source drift")
    start = source.index(b"    rule_ids = fields.Many2many(")
    end = source.index(b"    require_code =", start)
    payroll[STRUCTURE] = (source[:start] + b'    rule_ids = fields.One2many(\n'
                          b'        "hr.salary.rule", "struct_id", string="Salary Rules", copy=True\n'
                          b'    )\n' + source[end:])
    source = account[ACCOUNT]
    require(sha(source) == ACCOUNT_SHA, "SyS payroll accounting source drift")
    source = source.replace(b'related="contract_id.journal_id", store=True',
                            b'related="struct_id.journal_id", store=False, readonly=True, copy=False')
    # The native journal follows the company's structure property. Retain
    # the inherited contract onchange and let the related field follow it.
    start = source.index(b'    @api.onchange("contract_id")')
    end = source.index(b"    def action_payslip_cancel(", start)
    account[ACCOUNT] = source[:start] + source[end:]
    for files, name, body in ((payroll, "step_sys_ownership", OWNERSHIP),
                              (account, "step_sys_journal", JOURNAL)):
        path = "models/" + name + ".py"
        require(path not in files, "SyS structure provider already present")
        files[path] = body
        files["models/__init__.py"] += b"\nfrom . import " + name.encode() + b"\n"
    return result


def build(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    require(output.is_relative_to(Path("/opt/steps-validation")) and not output.exists()
            and not output.is_relative_to(source), "New private SyS engine output required")
    original = {m: _snapshot(source / m) for m in ("payroll", "payroll_account")}
    result = plan(original)
    with TemporaryDirectory(dir=output.parent) as scratch:
        top = Path(scratch) / "engine"
        for module, files in result.items():
            for name, body in files.items():
                path = top / module / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            require(_snapshot(top / module) == files, "SyS structure engine verification failed")
        top.rename(output)
    return {m: seal(hashes(files)) for m, files in result.items()}
